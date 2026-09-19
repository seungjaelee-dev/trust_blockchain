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
        self.assertTrue(any("MAX_SUPPLY" in r and re.search(r"mint\(address,uint256\), [0-9, ]*\b16\b", r)
                            for r in mint["reasons"]))
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

    def test_public_summaries_are_merged_and_paths_grouped(self):
        cases = {p.name: p.read_text(encoding="utf-8") for p in (test_expanded.ROOT / "reference/public").glob("*.sol")}
        results = self.analyze(cases)
        for item in results.values():
            self.assert_links(item)
            conclusions = [r for r in item['reasons'] if '근거·사용자 영향:' in r]
            self.assertEqual(len(conclusions), 1, item)
            self.assertLessEqual(len(item['reasons']), 7, item)
            self.assertTrue(any('상태 변화·외부 실행:' in r for r in item['reasons']))
        p3 = results['P3_Honeypot.sol']
        self.assertTrue(any('권한:' in r and 'whitelist[account]' in r for r in p3['reasons']))
        self.assertTrue(any('성공 조건:' in r and 'balanceOf[to]' in r for r in p3['reasons']))

    def test_distinct_risks_in_one_contract_are_not_collapsed(self):
        code = (test_expanded.DIRECTORY / 'allowance_risk.sol').read_text(encoding='utf-8')
        # Use the pre-stage1 owner issuance rule to test report separation.
        code = code.replace('uint256 public totalSupply;', 'uint256 public totalSupply; address public administrator;')
        code = code.replace('constructor(uint256 initialSupply) {', 'constructor(uint256 initialSupply) { administrator = msg.sender;')
        code = code.rsplit('}', 1)[0] + '''
        function issue(address to, uint256 amount) external {
            require(msg.sender == administrator);
            totalSupply += amount;
            balanceOf[to] += amount;
        }
        function take(address from, address to, uint256 amount) external {
            balanceOf[from] -= amount;
            balanceOf[to] += amount;
        }
        }
        '''
        item = self.analyze({'combined.sol': code})['combined.sol']
        self.assertEqual(item['verdict'], 'MALICIOUS')
        self.assert_links(item)
        summaries = [r for r in item['reasons'] if '판정 근거·사용자 영향:' in r]
        # Two independent unauthorized transfer entrypoints and an issuance risk.
        self.assertEqual(len(summaries), 3, summaries)
        for name in ['issue(address,uint256)', 'take(address,address,uint256)', 'transferFrom(address,address,uint256)']:
            self.assertTrue(any(name in r for r in summaries), summaries)

    def test_external_call_and_reset_order_is_preserved(self):
        cases = {name: (test_expanded.DIRECTORY / name).read_text(encoding='utf-8')
                 for name in ['reentry_risk.sol', 'reentry_safe.sol']}
        results = self.analyze(cases)
        for name, item in results.items():
            self.assert_links(item)
            flow = next(r for r in item['reasons'] if '상태 변화·외부 실행:' in r and '`call`' in r)
            if name == 'reentry_risk.sol':
                self.assertLess(flow.index('`call`'), flow.index('`0` 기록'))
            else:
                self.assertGreater(flow.index('`call`'), flow.index('`0` 기록'))


if __name__ == "__main__":
    unittest.main()
