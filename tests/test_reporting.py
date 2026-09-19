"""The cited statements must follow actual source nodes, not fixture offsets."""
import re
import unittest
import test_expanded
import test_ledger_operations


class ReportingTests(unittest.TestCase):
    analyze = test_expanded.ExpandedTests.analyze

    def assert_links(self, item):
        self.assertEqual(set(item), {"file", "verdict", "reasons", "evidence"})
        actual = {(e.get("function"), e["line"]) for e in item["evidence"]}
        self.assertEqual(len(actual), len(item["evidence"]))
        self.assertEqual(len(set(item["reasons"])), len(item["reasons"]))
        linked = set()
        for reason in item["reasons"]:
            self.assertTrue(reason.startswith("["), reason)
            prefix = reason[1:reason.index("] ")]
            for group in prefix.split(" · "):
                match = re.fullmatch(r"(.+?), ([0-9, ]+)행", group)
                if match:
                    function, lines = match.groups()
                    for line in lines.split(","):
                        ref = (None if function == "상태 선언" else function, int(line))
                        self.assertIn(ref, actual, reason)
                        linked.add(ref)
        self.assertTrue(actual <= linked, (actual - linked, item))

    def test_authority_condition_and_writes_are_cited(self):
        source = test_ledger_operations.source
        cases = {name: source(name) for name in ["admin_exemption.sol", "approval_bypass.sol", "bounded_issuance.sol", "self_burn.sol"]}
        result = self.analyze(cases)
        for name, item in result.items():
            self.assert_links(item)
        gate = result["admin_exemption.sol"]
        for needle in ['require(msg.sender == admin', 'paused = value', '!paused ||', 'balanceOf[msg.sender] -=', 'balanceOf[to] +=']:
            line = next(i for i, s in enumerate(cases[gate["file"]].splitlines(), 1) if needle in s)
            self.assertIn(line, [e["line"] for e in gate["evidence"]])
        self.assertIn("14행", gate["reasons"][0])
        self.assertIn("17", gate["reasons"][0])
        mint = result["bounded_issuance.sol"]
        self.assertTrue(any("MAX_SUPPLY" in r and "16행" in r for r in mint["reasons"]))
        self.assertFalse(any("정지 조건" in r for r in result["self_burn.sol"]["reasons"]))

    def test_names_line_shifts_and_branch_polarity(self):
        original = test_ledger_operations.source("approval_bypass.sol")
        changed = "// 🦊 위치를 바꿉니다\n\n\n" + original.replace("controller", "keeper").replace("transferFrom", "move")
        results = self.analyze({"a.sol": original, "b.sol": changed})
        a, b = results["a.sol"], results["b.sol"]
        self.assertEqual(a["verdict"], b["verdict"])
        self.assert_links(b)
        self.assertEqual({e['line'] + 3 for e in a['evidence']}, {e['line'] for e in b['evidence']})
        text = " ".join(b["reasons"])
        self.assertIn("keeper", text)
        self.assertNotIn("controller", text)
        self.assertIn("move(address,address,uint256)", text)
        self.assertIn("msg.sender != keeper", text)
        self.assertIn("호출자가 `keeper`", text)

    def test_unsupported_operation_has_local_evidence(self):
        code = test_ledger_operations.source("self_burn.sol").replace("totalSupply -= amount;", "totalSupply -= amount / 2;")
        result = self.analyze({"division.sol": code})["division.sol"]
        self.assertEqual(result["verdict"], "UNCERTAIN")
        self.assert_links(result)
        line = next(i for i, text in enumerate(code.splitlines(), 1) if "amount / 2" in text)
        self.assertIn(line, [e["line"] for e in result["evidence"]])
        self.assertTrue(any("DIVISION" in reason for reason in result["reasons"]))

    def test_two_risks_keep_their_own_locations(self):
        folder = test_expanded.DIRECTORY
        mint = (folder / "internal_risk.sol").read_text(encoding="utf-8")
        vault = (folder / "withdraw_risk.sol").read_text(encoding="utf-8")
        # A second SPDX declaration is invalid in a single Solidity source.
        vault = "\n".join(line for line in vault.splitlines() if not line.startswith("// SPDX"))
        item = self.analyze({"two.sol": mint + "\n" + vault})["two.sol"]
        self.assertEqual(item["verdict"], "MALICIOUS")
        self.assert_links(item)
        issuance = next(r for r in item["reasons"] if "보유자 지분을 희석" in r)
        withdrawal = next(r for r in item["reasons"] if "금고 전체 ETH" in r)
        self.assertIn("_issue(address,uint256)", issuance)
        self.assertNotIn("sweep()", issuance)
        self.assertIn("sweep()", withdrawal)
        self.assertNotIn("_issue(address,uint256)", withdrawal)


if __name__ == "__main__":
    unittest.main()
