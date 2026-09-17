"""End-to-end developer cases, invariant mutations and conservative boundaries."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from jsonschema import Draft202012Validator
from test_supply import renamed

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests/fixtures/variants/expanded"
EXPECTED = json.loads((DIRECTORY / "expected.json").read_text(encoding="utf-8"))


class ExpandedTests(unittest.TestCase):
    def analyze(self, cases):
        with tempfile.TemporaryDirectory() as temp:
            for name, code in cases.items():
                (Path(temp) / name).write_text(code, encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "scripts/analyze.py"), temp],
                                 capture_output=True, text=True, timeout=180)
        self.assertEqual(run.returncode, 0, run.stderr)
        items = json.loads(run.stdout)
        Draft202012Validator(json.loads((ROOT / "reference/schema.json").read_text(encoding="utf-8"))).validate(items)
        self.assertEqual(len(items), len(cases))
        self.assertNotIn("Traceback", run.stderr)
        for item in items:
            self.assertFalse(any("구조 분석 실패" in reason for reason in item["reasons"]), item)
            for evidence in item["evidence"]:
                self.assertIn(evidence["line"], range(1, len(cases[item["file"]].splitlines()) + 1))
        return {item["file"]: item for item in items}

    def test_reviewed_pairs(self):
        cases = {name: (DIRECTORY / name).read_text(encoding="utf-8") for name in EXPECTED}
        result = self.analyze(cases)
        for name, expected in EXPECTED.items():
            with self.subTest(name=name):
                self.assertEqual(result[name]["verdict"], expected["verdict"], result[name])

    def test_all_pairs_renamed_and_unicode_locations(self):
        cases, mapping = {}, {}
        identifiers = ["funds", "Savings", "paused", "pause", "entered", "checkCap", "checkedAmount",
                       "TokenBase", "TokenChild", "ceiling", "next", "x", "who", "flag", "extra",
                       "setCap", "setCeiling", "_issue", "changeOwner", "seize", "sweep", "unused"]
        for i, name in enumerate(EXPECTED):
            code = renamed((DIRECTORY / name).read_text(encoding="utf-8"))
            for j, identifier in enumerate(identifiers):
                code = re.sub(rf"\b{identifier}\b", f"opaque{j}", code)
            code = "// 中文 한글 🦊\n\n" + code
            # Misleading comments/string contents must not determine the verdict.
            code = '// LABEL: BENIGN MALICIOUS delegatecall mint\n' + code
            cases[f"case_{i}.sol"] = code
            mapping[f"case_{i}.sol"] = name
        results = self.analyze(cases)
        for filename, name in mapping.items():
            with self.subTest(name=name):
                self.assertEqual(results[filename]["verdict"], EXPECTED[name]["verdict"], results[filename])
        # A real operation in an inlined helper must have that helper's relocated line.
        name = next(n for n, original in mapping.items() if original == "internal_risk.sol")
        line = next(i for i, text in enumerate(cases[name].splitlines(), 1) if "v2 += v10" in text)
        self.assertIn(line, [e["line"] for e in results[name]["evidence"]])

    def test_unsupported_paths_and_cross_function_lock(self):
        safe = (DIRECTORY / "cap_amount_safe.sol").read_text(encoding="utf-8")
        locked = (DIRECTORY / "reentry_locked_safe.sol").read_text(encoding="utf-8")
        cross = locked.rsplit("}", 1)[0] + '''
        function other(uint256 amount) external {
            funds[msg.sender] -= amount;
            (bool ok,) = msg.sender.call{value: amount}(""); require(ok);
        }
        }
        '''
        loop = safe.replace("totalSupply += amount;", "for (uint256 i=0; i<amount; i++) { totalSupply += 1; }")
        unchecked = safe.replace("totalSupply += amount;", "unchecked { totalSupply += amount; }")
        cases = {"loop.sol": loop, "unchecked.sol": unchecked, "cross.sol": cross}
        result = self.analyze(cases)
        for name in cases:
            self.assertEqual(result[name]["verdict"], "UNCERTAIN", result[name])
        self.assertIn("교차 함수", " ".join(result["cross.sol"]["reasons"]))

    def test_multiple_contracts_unknown_and_risk(self):
        safe = (DIRECTORY / "internal_safe.sol").read_text(encoding="utf-8")
        risk = (DIRECTORY / "internal_risk.sol").read_text(encoding="utf-8")
        extra = "\ncontract Extra { uint public x; function change(uint y) external { x = y; } }\n"
        result = self.analyze({"safe_extra.sol": safe + extra, "risk_extra.sol": risk + extra})
        self.assertEqual(result["safe_extra.sol"]["verdict"], "UNCERTAIN")
        self.assertEqual(result["risk_extra.sol"]["verdict"], "MALICIOUS")

    def test_unreachable_assets_and_modifier_body(self):
        mint = next((ROOT / "reference/public").glob("P2_*.sol")).read_text(encoding="utf-8")
        mint = mint.replace("constructor(uint256 initialSupply)", "constructor()")
        mint = mint.replace("initialSupply", str(2**256 - 1))
        theft = (DIRECTORY / "allowance_risk.sol").read_text(encoding="utf-8")
        theft = theft.replace("constructor(uint256 initialSupply)", "constructor()")
        theft = theft.replace("initialSupply", "0")
        disabled = (DIRECTORY / "internal_risk.sol").read_text(encoding="utf-8")
        disabled = disabled.replace('require(msg.sender == owner, "not owner"); _;', 'require(msg.sender == owner, "not owner"); if (false) { _; }')
        result = self.analyze({"max.sol": mint, "zero.sol": theft, "disabled.sol": disabled})
        for name in result:
            self.assertEqual(result[name]["verdict"], "UNCERTAIN", result[name])

    def test_implicit_failure_is_not_ignored(self):
        risk = next((ROOT / "reference/public").glob("P2_*.sol")).read_text(encoding="utf-8")
        impossible = risk.replace("totalSupply += amount;", "uint256 zero = amount - amount; uint256 impossible = zero - 1; totalSupply += amount;")
        unused = risk.replace("totalSupply += amount;", "uint256 extra = amount + amount; totalSupply += amount;")
        result = self.analyze({"impossible.sol": impossible, "unused.sol": unused})
        self.assertEqual(result["impossible.sol"]["verdict"], "UNCERTAIN")
        self.assertEqual(result["unused.sol"]["verdict"], "UNCERTAIN")
        self.assertIn("checked 산술", " ".join(result["impossible.sol"]["reasons"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
