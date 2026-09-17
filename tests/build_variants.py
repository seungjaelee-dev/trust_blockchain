"""개발 평가용 문제 생성. 런타임 분석기는 이 파일/정답을 읽지 않는다.

사용자가 2026-09-17 기대 판정 검토와 테스트 사이클을 위임했다.
원본 MIT 고지를 보존하며 LABEL/설명은 제거한다. 새 사례는 기대 근거를 먼저 기록한다.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests/fixtures/variants/expanded"


def source(n):
    code = next((ROOT / "reference/public").glob(f"P{n}_*.sol")).read_text(encoding="utf-8")
    return re.sub(r"//(?! SPDX-License-Identifier:)[^\n]*", "", code)


def add_function(code, body):
    return code.rsplit("}", 1)[0] + body + "\n}\n"


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {}

    def put(name, code, verdict, reason):
        (OUT / (name + ".sol")).write_text(code, encoding="utf-8")
        cases[name + ".sol"] = {"verdict": verdict, "reason": reason}

    p1, p3, p4, p5 = source(1), source(3), source(4), source(5)
    cap = 'require(totalSupply + amount <= MAX_SUPPLY, "cap exceeded");'
    for safe in (True, False):
        suffix = "safe" if safe else "risk"
        branch = p4.replace("uint256 amount) external onlyOwner", "uint256 amount, bool checkCap) external onlyOwner")
        branch = branch.replace(cap, f"if (checkCap) {{ {cap} }}" + (f" else {{ {cap} }}" if safe else ""))
        put("cap_branch_" + suffix, branch, "BENIGN" if safe else "MALICIOUS",
            "양 갈래 모두 같은 증가량을 제한" if safe else "false 입력으로 상한 검사 우회 후 발행 가능")
        mismatch = p4.replace("uint256 amount) external onlyOwner", "uint256 amount, uint256 checkedAmount) external onlyOwner")
        if not safe:
            mismatch = mismatch.replace("totalSupply + amount <=", "totalSupply + checkedAmount <=")
        put("cap_amount_" + suffix, mismatch, "BENIGN" if safe else "MALICIOUS",
            "실제 증가량 검사" if safe else "0을 검사하고 별도의 큰 amount로 발행 가능")
        mutable = p4.replace("uint256 public constant MAX_SUPPLY =", "uint256 public MAX_SUPPLY =")
        setter = 'function setCap(uint256 next) external onlyOwner { '
        setter += 'require(next <= 1_000_000e18, "ceiling"); ' if safe else ""
        mutable = add_function(mutable, setter + "MAX_SUPPLY = next; }")
        put("cap_mutable_" + suffix, mutable, "BENIGN" if safe else "MALICIOUS",
            "변경 가능하지만 고정된 최종 천장을 지킴" if safe else "관리자가 상한을 임의로 올린 뒤 발행 가능")
        second = add_function(p4, "function extra(address to, uint256 amount) external onlyOwner { " +
                              (cap if safe else "") + " totalSupply += amount; balanceOf[to] += amount; }")
        put("cap_second_" + suffix, second, "BENIGN" if safe else "MALICIOUS",
            "두 발행 함수 모두 상한 강제" if safe else "두 번째 외부 함수가 상한 우회")
        internal = p4.replace("        " + cap, "        _issue(to, amount);\n    }\n    function _issue(address to, uint256 amount) internal {\n        " + (cap if safe else ""))
        put("internal_" + suffix, internal, "BENIGN" if safe else "MALICIOUS",
            "내부 함수의 실제 증가량 상한 검사" if safe else "내부 함수에 옮겨진 무상한 발행")
        allowance = p1
        if not safe:
            allowance = allowance.replace('require(allowance[from][msg.sender] >= value, "not allowed");', "")
            allowance = allowance.replace("allowance[from][msg.sender] -= value;", "")
        put("allowance_" + suffix, allowance, "BENIGN" if safe else "MALICIOUS",
            "당사자 승인 검사 및 사용분 차감" if safe else "피해자 승인 없이 제3자가 잔액 이동 가능")
        paused = p4.replace("    event Transfer", "    bool public paused;\n    event Transfer", 1)
        paused = add_function(paused, "function pause(bool flag) external onlyOwner { paused = flag; }")
        restriction = 'require(!paused, "paused");' if safe else 'require(!paused || msg.sender == owner, "paused");'
        paused = paused.replace('require(balanceOf[msg.sender] >= value, "insufficient");', restriction + '\n        require(balanceOf[msg.sender] >= value, "insufficient");')
        put("pause_" + suffix, paused, "BENIGN" if safe else "MALICIOUS",
            "정지 제약은 관리자에게도 동일하게 적용" if safe else "관리자가 정지시켜도 자신은 전송 가능")

    # 고정 공급량 + 관리자 변경 쌍. 권한 변경을 실제 잔액 탈취 권한과 연결한다.
    base = p1.replace("    event Transfer", "    address public owner;\n    event Transfer", 1)
    base = base.replace("        totalSupply = initialSupply;", "        owner = msg.sender;\n        totalSupply = initialSupply;")
    for safe in (True, False):
        # 안전본은 정상 관리권 이전만 있고, 위험본은 무단 권한 획득 + 피해자 자산 이동.
        body = "function changeOwner(address next) external { " + ('require(msg.sender == owner, "owner"); ' if safe else "") + "owner = next; }"
        if not safe:
            body += "\nfunction seize(address from, address to, uint256 amount) external { require(msg.sender == owner); balanceOf[from] -= amount; balanceOf[to] += amount; }"
        put("ownership_" + ("safe" if safe else "risk"), add_function(base, body), "BENIGN" if safe else "MALICIOUS",
            "기존 소유자만 관리권 이전, 사용자 잔액 임의 변경 기능 없음" if safe else "임의 관리권 획득 후 남의 토큰 이동; seize 자체도 관리자 탈취 경로")

    vault = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract Savings {
    address public owner;
    mapping(address => uint256) public funds;
    constructor() { owner = msg.sender; }
    function deposit() external payable { funds[msg.sender] += msg.value; }
    function withdraw(uint256 amount) external {
        require(funds[msg.sender] >= amount);
        funds[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok);
    }
}
'''
    put("withdraw_safe", vault, "BENIGN", "자기 예치금 차감 후 같은 금액을 본인에게 송금")
    put("withdraw_risk", add_function(vault, 'function sweep() external { require(msg.sender == owner); (bool ok,) = owner.call{value: address(this).balance}(""); require(ok); }'),
        "MALICIOUS", "사용자 예치금을 관리자에게 전액 송금")
    no_deposit = re.sub(r"    function deposit\(\).*?\n", "", vault)
    no_deposit = add_function(no_deposit, 'function sweep() external { require(msg.sender == owner); (bool ok,) = owner.call{value: address(this).balance}(""); require(ok); }')
    put("force_send_safe", no_deposit, "BENIGN", "예치 경로와 다른 사용자 자산 없음; 강제 ETH는 대회 귀속 가정상 사용자 자산 아님")
    reentrant = vault.replace("function withdraw(uint256 amount) external {\n        require(funds[msg.sender] >= amount);\n        funds[msg.sender] -= amount;", "function withdraw() external {\n        uint256 amount = funds[msg.sender];\n        require(amount > 0);")
    reentrant = reentrant.replace("        require(ok);", "        require(ok);\n        funds[msg.sender] = 0;")
    put("reentry_risk", reentrant, "MALICIOUS", "송금 시 장부가 그대로이며 재호출 가능, 복귀 후 0 대입으로 중복 지급이 취소되지 않음")
    put("reentry_safe", reentrant.replace('        (bool ok,)', '        funds[msg.sender] = 0;\n        (bool ok,)').replace('        require(ok);\n        funds[msg.sender] = 0;', '        require(ok);'),
        "BENIGN", "송금 전에 예치금을 0으로 만들어 같은 돈의 재출금 차단")
    # 검사 위치가 뒤라는 이유만으로 악성이라고 해서는 안 된다: 실패 시 거래 전체 rollback.
    put("postcheck_safe", p4.replace("        " + cap, "").replace("        balanceOf[to] += amount;", '        balanceOf[to] += amount;\n        require(totalSupply <= MAX_SUPPLY, "cap");'),
        "BENIGN", "외부 호출 없는 거래의 사후 검사 실패는 앞선 증가까지 취소")
    put("dead_branch_safe", p4.replace(cap, 'if (false) { totalSupply += amount; balanceOf[to] += amount; }\n        ' + cap),
        "BENIGN", "도달 불가능한 발행 코드를 위험 근거로 사용하지 않음")
    put("revert_branch_safe", p4.replace(cap, 'if (totalSupply + amount > MAX_SUPPLY) { revert("cap"); }'),
        "BENIGN", "초과 분기는 revert하고 성공하는 경로는 상한 이하")
    put("allowance_implicit_safe", p1.replace('        require(allowance[from][msg.sender] >= value, "not allowed");', ""),
        "BENIGN", "0.8 checked 승인 차감의 underflow 실패도 승인 한도를 강제")
    put("allowance_reuse_risk", p1.replace("        allowance[from][msg.sender] -= value;", ""),
        "MALICIOUS", "사용한 승인을 차감하지 않아 승인 총량보다 반복 전송 가능")
    put("unused_list_safe", p3.replace('        require(whitelist[msg.sender], "trading locked");', ""),
        "BENIGN", "사용되지 않는 허용 목록은 실제 전송을 제한하지 않음")
    put("delegate_risk", p5, "MALICIOUS", "사용자 예치금과 소유자 임의 delegatecall 연결")
    put("delegate_no_deposit_safe", re.sub(r"    function deposit\(\) external payable \{.*?\n    \}", "", p5, flags=re.S),
        "BENIGN", "예치 없는 force-send만의 대회 경계, 다른 사용자 자산 없음")
    for safe in (True, False):
        inherited = p4.replace("contract CappedToken", "abstract contract TokenBase")
        if not safe:
            inherited = inherited.replace(cap, "")
        put("inherited_" + ("safe" if safe else "risk"), inherited + "\ncontract TokenChild is TokenBase {}\n",
            "BENIGN" if safe else "MALICIOUS", "같은 파일의 부모 함수/상태를 상속, 실제 발행 상한 유무를 판정")
    fake_bound = p4.replace("uint256 public constant MAX_SUPPLY =", "uint256 public MAX_SUPPLY =")
    fake_bound = fake_bound.replace("    address public owner;", "    uint256 public ceiling = 1_000_000e18;\n    address public owner;")
    fake_bound = add_function(fake_bound, "function setCeiling(uint256 x) external onlyOwner { ceiling = x; }\nfunction setCap(uint256 x) external onlyOwner { require(x <= ceiling); MAX_SUPPLY = x; }")
    put("cap_moving_ceiling_risk", fake_bound, "MALICIOUS", "상한의 천장도 임의로 변경 가능하여 고정 경계가 아님")
    put("cap_per_call_risk", p4.replace(cap, 'require(amount <= MAX_SUPPLY, "one call");'),
        "MALICIOUS", "한 번의 수량만 제한하며 반복 발행 총량은 제한하지 않음")
    put("contradictory_safe", p4.replace(cap, 'if (amount > MAX_SUPPLY) { require(amount <= MAX_SUPPLY); totalSupply += amount; balanceOf[to] += amount; }\n' + cap),
        "BENIGN", "모순 조건을 모두 만족해야 하는 위험 경로는 실행 불가능")
    put("unreachable_internal_safe", add_function(p4, "function unused(uint256 x) private { totalSupply += x; balanceOf[owner] += x; }"),
        "BENIGN", "아무도 호출하지 않는 private 발행 함수는 실행 경로 아님")
    put("zero_mint_safe", p4.replace(cap, "require(amount == 0);"),
        "BENIGN", "상한 검사는 없지만 발행량이 반드시 0이라 위험 발행 아님")
    late = vault.replace("        funds[msg.sender] -= amount;", "").replace("        require(ok);", "        require(ok);\n        funds[msg.sender] -= amount;")
    put("late_checked_safe", late, "BENIGN", "이 제한된 금고는 매 지급분을 checked 차감; 잔액 초과 중첩 지급은 전체 취소")
    locked = reentrant.replace("    address public owner;", "    bool private entered;\n    address public owner;")
    locked = locked.replace("function withdraw() external {", "function withdraw() external {\n        require(!entered);\n        entered = true;")
    locked = locked.replace("        funds[msg.sender] = 0;", "        funds[msg.sender] = 0;\n        entered = false;")
    put("reentry_locked_safe", locked, "BENIGN", "실제 bool 잠금이 송금 중 같은 출금 재진입을 차단")
    # Protected and unprotected control over the vault's delegate target: address setter matters.
    for safe in (True, False):
        gate = p4.replace("modifier onlyOwner() { require(msg.sender == owner, \"not owner\"); _; }", "modifier onlyOwner(address who) { require(msg.sender == who); _; }")
        gate = gate.replace("external onlyOwner {", "external onlyOwner(owner) {")
        if not safe:
            gate = gate.replace(cap, "")
        put("modifier_argument_" + ("safe" if safe else "risk"), gate, "BENIGN" if safe else "MALICIOUS",
            "modifier 인자를 실제 owner 선언에 연결한 상한 발행/무상한 발행")
    (OUT / "expected.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} development fixtures")


if __name__ == "__main__":
    build()
