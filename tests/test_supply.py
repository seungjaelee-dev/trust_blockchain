"""평가용 소스 변형. 분석기 패키지는 이 파일이나 정답을 읽지 않는다."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "reference/schema.json").read_text(encoding="utf-8"))


def source(number):
    return next((ROOT / "reference/public").glob(f"P{number}_*.sol")).read_text(encoding="utf-8")


def renamed(code):
    # 테스트 원본에는 // 주석만 존재. 변환 로직은 분석기에서 사용하지 않는다.
    code = re.sub(r"//[^\n]*", "", code)
    identifiers = ["HiddenMint", "CappedToken", "totalSupply", "balanceOf", "owner", "MAX_SUPPLY",
                   "onlyOwner", "mint", "transfer", "distributeRewards", "amount", "value", "to",
                   "initialSupply", "Transfer", "Mint", "name", "symbol", "decimals",
                   "StandardToken", "RewardPool", "Vault", "allowance", "approve", "transferFrom",
                   "spender", "from", "Approval", "whitelist", "setWhitelist", "account", "allowed",
                   "deposits", "deposit", "withdraw", "execute", "target", "data", "ok", "Deposited", "Withdrawn"]
    for number, identifier in enumerate(identifiers):
        # msg.value와 call{value: ...}는 사용자 식별자가 아닌 언어 내장 표기다.
        code = re.sub(rf"(?<!\.)\b{identifier}\b(?!\s*:)", f"v{number}", code)
    # 주석의 Unicode 바이트 수가 줄 위치를 오염시키지 않아야 한다.
    return "// 한글 주석 🐢\n\n" + code.replace(";", ";\n\n")


class SupplyTests(unittest.TestCase):
    def analyze(self, cases):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name, code in cases.items():
                (directory / name).write_text(code, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/analyze.py"), str(directory)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            results = json.loads(completed.stdout)
            Draft202012Validator(SCHEMA).validate(results)
            self.assertNotIn("Traceback", completed.stderr)
            for item in results:
                self.assertFalse(any("분석 실패" in reason for reason in item["reasons"]), completed.stderr)
                for item_evidence in item["evidence"]:
                    self.assertLessEqual(item_evidence["line"], len(cases[item["file"]].splitlines()))
            return {item["file"]: item for item in results}

    def test_renaming_comments_whitespace_unicode_and_locations(self):
        cases = {"a.sol": renamed(source(2)), "b.sol": renamed(source(4))}
        results = self.analyze(cases)
        self.assertEqual(results["a.sol"]["verdict"], "MALICIOUS")
        self.assertEqual(results["b.sol"]["verdict"], "BENIGN")
        self.assertIn("공급량 상한 검사가 없어", results["a.sol"]["reasons"][0])
        self.assertIn("상수 상한 이하", results["b.sol"]["reasons"][0])
        for name, needle in (("a.sol", "v2 += v10"), ("b.sol", "require(v2 + v10 <= v5")):
            line = next(i for i, text in enumerate(cases[name].splitlines(), 1) if needle in text)
            self.assertEqual(results[name]["evidence"][0]["line"], line)

    def test_assignment_spelling_preserves_relations(self):
        code = source(4).replace("totalSupply += amount", "totalSupply = totalSupply + amount")
        code = code.replace("balanceOf[to] += amount", "balanceOf[to] = balanceOf[to] + amount")
        self.assertEqual(self.analyze({"a.sol": code})["a.sol"]["verdict"], "BENIGN")

    def test_public_p2_p4_together_aggregates_risk(self):
        code = source(4) + "\n" + source(2).replace("// SPDX-License-Identifier: MIT", "// MIT (same license as above)")
        item = self.analyze({"a.sol": code})["a.sol"]
        self.assertEqual(item["verdict"], "MALICIOUS")
        line = next(i for i, text in enumerate(code.splitlines(), 1) if "totalSupply += amount" in text and i > len(source(4).splitlines()))
        self.assertEqual(item["evidence"][0]["line"], line)

    def test_fixed_supply_restriction_delegate_renamed(self):
        cases = {"a.sol": renamed(source(1)), "b.sol": renamed(source(3)), "c.sol": renamed(source(5))}
        results = self.analyze(cases)
        for name, verdict in (("a.sol", "BENIGN"), ("b.sol", "MALICIOUS"), ("c.sol", "MALICIOUS")):
            self.assertEqual(results[name]["verdict"], verdict, results[name])
        # 근거가 변형된 소스의 해당 연산을 가리키는지 확인한다.
        for name, needle in (("b.sol", '"trading locked"'), ("c.sol", ".delegatecall(")):
            line = next(i for i, text in enumerate(cases[name].splitlines(), 1) if needle in text)
            self.assertIn(line, [e["line"] for e in results[name]["evidence"]])

    def test_reviewed_cap_variants(self):
        directory = ROOT / "tests/fixtures/variants/r1"
        cases = {p.name: p.read_text(encoding="utf-8") for p in directory.glob("*.sol")}
        results = self.analyze(cases)
        self.assertEqual(results["cap_removed.sol"]["verdict"], "MALICIOUS")
        self.assertEqual(results["cap_bypass.sol"]["verdict"], "MALICIOUS")
        self.assertIn("검사 우회", results["cap_bypass.sol"]["reasons"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
