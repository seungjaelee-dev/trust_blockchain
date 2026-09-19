"""Reviewed source pairs and adversarial mutations for ledger coverage.

Synthetic dataset labels are not authoritative: the administrator exemption is
MALICIOUS under the challenge contract, unreachable third-party loss is unknown.
"""
from pathlib import Path
import re
import unittest
import test_expanded

DIRECTORY = Path(__file__).parent / "fixtures/variants/ledger"
EXPECTED = {
    "self_burn.sol": "BENIGN", "delegated.sol": "BENIGN",
    "deposit_cap.sol": "BENIGN", "approved_burn.sol": "BENIGN",
    "symmetric_pause.sol": "BENIGN", "bounded_issuance.sol": "BENIGN",
    "approval_bypass.sol": "MALICIOUS", "destination_block.sol": "MALICIOUS",
    "arbitrary_payment.sol": "MALICIOUS", "selective_block.sol": "MALICIOUS",
    "admin_exemption.sol": "MALICIOUS", "unreachable_burn.sol": "UNCERTAIN",
    "nontransferable_mint.sol": "UNCERTAIN", "wallet.sol": "UNCERTAIN",
}


def source(name):
    return (DIRECTORY / name).read_text(encoding="utf-8")


class LedgerTests(unittest.TestCase):
    analyze = test_expanded.ExpandedTests.analyze

    def check(self, cases, expected):
        actual = self.analyze(cases)
        for name, verdict in expected.items():
            with self.subTest(name=name):
                self.assertEqual(actual[name]["verdict"], verdict, actual[name])
        return actual

    def test_reviewed_sources(self):
        self.check({n: source(n) for n in EXPECTED}, EXPECTED)

    def test_opaque_names_and_unicode(self):
        cases, expected = {}, {}
        for i, (name, verdict) in enumerate(EXPECTED.items()):
            code = source(name)
            words = {"balanceOf", "totalSupply", "owner", "controller", "guardian",
                     "admin", "allowance", "burnAllowance", "deposits", "mint", "burn",
                     "market", "exitsOpen", "permitted", "paused", "USER_CAP", "MAX_SUPPLY"}
            words.update(re.findall(r"contract\s+(\w+)", code))
            for j, word in enumerate(sorted(words)):
                code = re.sub(rf"\b{word}\b", f"opaque{j}", code)
            file = f"sample_{i}.sol"
            cases[file] = "// 한글 🦊 misleading LABEL BENIGN MALICIOUS\n\n" + code
            expected[file] = verdict
        self.check(cases, expected)

    def test_permissions_and_burn_invariants(self):
        delegated = source("delegated.sol")
        burn = source("approved_burn.sol")
        cases = {
            "reuse.sol": delegated.replace("allowance[from][msg.sender] -= amount;", ""),
            "wrong_index.sol": delegated.replace("allowance[from][msg.sender] -= amount;", "allowance[to][msg.sender] -= amount;"),
            "wrong_amount.sol": delegated.replace("allowance[from][msg.sender] -= amount;", "allowance[from][msg.sender] -= 1;"),
            "burn_reuse.sol": burn.replace("burnAllowance[from][msg.sender] -= amount;", ""),
            "burn_mismatch.sol": burn.replace("totalSupply -= amount;", "totalSupply -= 1;"),
            "burn_reordered.sol": burn.replace("balanceOf[from] -= amount;\n        totalSupply -= amount;", "totalSupply -= amount;\n        balanceOf[from] -= amount;"),
            "zero.sol": source("approval_bypass.sol").replace("balanceOf[msg.sender] = supply;", "balanceOf[msg.sender] = 0;"),
            "no_approval.sol": delegated.replace("allowance[from][msg.sender] -= amount;", "").replace("allowance[msg.sender][spender] = amount;", ""),
            "zero_approval.sol": source("approval_bypass.sol").replace("allowance[msg.sender][spender] = amount;", "require(amount == 0); allowance[msg.sender][spender] = amount;"),
        }
        self.check(cases, {"reuse.sol": "MALICIOUS", "wrong_index.sol": "UNCERTAIN",
                           "wrong_amount.sol": "UNCERTAIN", "burn_reuse.sol": "MALICIOUS",
                           "burn_mismatch.sol": "UNCERTAIN", "burn_reordered.sol": "BENIGN",
                           "zero.sol": "UNCERTAIN", "no_approval.sol": "UNCERTAIN", "zero_approval.sol": "UNCERTAIN"})

    def test_reachable_privileged_burn(self):
        base = source("unreachable_burn.sol")
        transfer = '''
        function move(address recipient, uint256 amount) external {
            balanceOf[msg.sender] -= amount;
            balanceOf[recipient] += amount;
        }
        '''
        enabled = base.rsplit("}", 1)[0] + transfer + "}"
        disabled = enabled.replace("function move(address recipient, uint256 amount) external {",
                                   "function move(address recipient, uint256 amount) external { require(amount == 0);")
        self.check({"enabled.sol": enabled, "disabled.sol": disabled},
                   {"enabled.sol": "MALICIOUS", "disabled.sol": "UNCERTAIN"})

    def test_deposit_and_payment_boundaries(self):
        cap = source("deposit_cap.sol")
        route = source("arbitrary_payment.sol")
        cases = {
            "wrong_credit.sol": cap.replace("deposits[msg.sender] += msg.value;", "deposits[msg.sender] += msg.value + 1;"),
            "wrong_payee.sol": cap.replace("payable(msg.sender)", "payable(address(1))"),
            "zero_cap.sol": cap.replace("103 ether", "0"),
            "positive.sol": cap.replace('require(deposits[msg.sender] + msg.value <= USER_CAP, "cap");', 'require(msg.value > 0); require(deposits[msg.sender] + msg.value <= USER_CAP);'),
            "route_zero.sol": route.replace("value: value", "value: 0"),
            "route_no_deposit.sol": route.replace("function deposit() external payable { deposits[msg.sender] += msg.value; }", ""),
            "route_capped.sol": route.replace("deposits[msg.sender] += msg.value;", "require(deposits[msg.sender] + msg.value <= 1 ether); deposits[msg.sender] += msg.value;"),
        }
        self.check(cases, {n: ("BENIGN" if n == "positive.sol" else "MALICIOUS" if n == "route_capped.sol" else "UNCERTAIN") for n in cases})

    def test_cap_and_gate_mutations(self):
        cap = source("bounded_issuance.sol")
        gate = source("destination_block.sol")
        cases = {
            "missing_cap.sol": cap.replace('require(totalSupply + amount <= MAX_SUPPLY, "cap");', ""),
            "wrong_cap.sol": cap.replace("totalSupply + amount <= MAX_SUPPLY", "amount <= MAX_SUPPLY"),
            "other_write.sol": cap.replace("balanceOf[to] += amount;", "balanceOf[to] += amount; balanceOf[msg.sender] += amount;"),
            "zero_gate.sol": gate.replace("balanceOf[msg.sender] = supply;", "balanceOf[msg.sender] = 0;"),
            "immutable_gate.sol": gate.replace("function setExit(bool value) external onlyOwner { exitsOpen = value; }", ""),
            "or_reversed.sol": source("admin_exemption.sol").replace("!paused || msg.sender == admin", "msg.sender == admin || !paused"),
            "owner_only.sol": source("admin_exemption.sol").replace('require(!paused || msg.sender == admin, "paused");', 'require(msg.sender == admin); require(!paused || msg.sender == admin, "paused");'),
            "cannot_pause.sol": source("admin_exemption.sol").replace("paused = value;", "require(!value); paused = value;"),
            "still_symmetric.sol": source("admin_exemption.sol").replace('require(!paused || msg.sender == admin, "paused");', 'require(!paused); require(!paused || msg.sender == admin, "paused");'),
        }
        self.check(cases, {n: "MALICIOUS" if n == "or_reversed.sol" else "BENIGN" if n == "still_symmetric.sol" else "UNCERTAIN" for n in cases})


if __name__ == "__main__":
    unittest.main()
