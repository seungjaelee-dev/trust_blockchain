"""ETH ledger schemas: own withdrawals, sweeps, delegatecall and stale-ledger payout.

Reentrancy coverage is intentionally limited to a cached full balance paid before
zeroing it. A late checked subtraction is NOT automatically called exploitable.
"""
from .linear import SENDER, VALUE, Unsupported, symbol
from .supply import is_balance, index, is_parameter, equal
from .paths import contract_paths, ETHER, ZERO, TRUE, FALSE, location_evidence, negate
from .expanded_tokens import initialized, owner_guard, guards, root, parameter_condition, result


def analyze_contract(contract):
    initial, runtime = contract_paths(contract)
    values, owners, _ = initialized(initial)
    ledgers = {v for v in contract.state_variables if is_balance(v)}
    if len(ledgers) != 1:
        raise Unsupported("단일 ETH 예치 장부를 식별하지 못했습니다.")
    ledger = ledgers.pop()
    if any(root(loc) == ledger for _, p in initial for loc, _, _ in p.writes):
        raise Unsupported("초기 예치 장부 쓰기는 지원하지 않습니다.")
    # Extra state could carry assets/roles outside this small vault model.
    locks = {v for v in contract.state_variables if str(v.type) == "bool" and values.get(v, FALSE) == FALSE}
    if any(v != ledger and v not in owners and v not in locks for v in contract.state_variables):
        raise Unsupported("추가 상태가 있는 금고의 자산/잠금 역할은 미지원입니다.")
    deposits, withdrawals, executions, sweeps, reentry, unknown = [], [], [], [], [], []
    payout_locks, late_reset_locks = [], []
    for function, path in runtime:
        loc = index(ledger, SENDER)
        conditions = guards(path)
        if function.payable:
            if (not conditions and not path.calls and len(path.writes) == 1
                    and path.writes[0][:2] == (loc, ("ADDITION", loc, VALUE))):
                deposits.append(path.writes[0][2])
            else:
                unknown.append("payable 수신 경로의 예치 기록/자산 귀속 미확인")
            continue
        if not path.calls:
            # Authorized ownership changes preserve the asset model.
            if (len(path.writes) == 1 and path.writes[0][0][0] == "variable"
                    and path.writes[0][0][1] in owners and owner_guard(path, owners)
                    and is_parameter(path.writes[0][1], function, "address")):
                continue
            if path.writes:
                unknown.append("호출 없는 추가 상태 변경 경로")
            continue
        if len(path.calls) != 1 or ("call_success", 0) not in conditions:
            unknown.append("외부 호출 성공 처리 미확인")
            continue
        call = path.calls[0]
        before = [g for g in conditions if g != ("call_success", 0)]
        ordinary_owner = owner_guard(path, owners) and all(any(equal(g, SENDER, symbol(v)) for v in owners) for g in before)
        if (call["kind"] == "delegatecall" and not path.writes and ordinary_owner
                and is_parameter(call["destination"], function, "address")
                and len(call["arguments"]) == 1 and is_parameter(call["arguments"][0], function, "bytes")):
            executions.append(call["node"])
            continue
        if call["kind"] != "call" or any(a[0] != "constant" or a[2] != "" for a in call["arguments"]):
            unknown.append("외부 코드/호출 데이터 영향 미확인")
            continue
        if (not path.writes and ordinary_owner and call["destination"] in {symbol(v) for v in owners}
                and call["value"] == ETHER):
            sweeps.append(call["node"])
            continue
        ledger_writes = [w for w in path.writes if root(w[0]) == ledger]
        lock_writes = [w for w in path.writes if root(w[0]) in locks]
        locked = False
        if len(lock_writes) == 2 and len(path.writes) == 3:
            (lock, enabled, enter), (unlock, disabled, leave) = lock_writes
            locked = (lock == unlock and enabled == TRUE and disabled == FALSE
                      and negate(lock) in before and path.writes[0] == lock_writes[0]
                      and path.writes[-1] == lock_writes[1] and call["writes_before"] >= 1)
        if call["destination"] != SENDER or len(ledger_writes) != 1 or (lock_writes and not locked):
            unknown.append("송금 수령자와 장부 차감의 연결 미확인")
            continue
        target, value, node = ledger_writes[0]
        quantity = call["value"]
        if target != loc:
            unknown.append("타인 장부/송금 관계 미확인")
            continue
        sub = quantity is not None and value == ("SUBTRACTION", loc, quantity)
        zero = value == ZERO and quantity == loc
        payout_locks.append(lock_writes[0][0] if locked else None)
        ledger_before = any(w == ledger_writes[0] for w in path.writes[:call["writes_before"]])
        if (sub or zero) and ledger_before:
            # Checked subtraction or full own-balance reset precedes handing control out.
            withdrawals.append(node)
            continue
        if (sub or zero) and locked:
            if zero:
                late_reset_locks.append(lock_writes[0][0])
            withdrawals.append(node)
            continue
        if sub and not lock_writes and len(path.writes) == 1:
            # Within this one-ledger schema every successful payout is charged;
            # an overdraw in nested calls reverts, including prior ETH transfers.
            withdrawals.append(node)
            continue
        if zero and call["writes_before"] == 0 and before in ([], [("LESS", ZERO, loc)]):
            reentry.append(call["node"])
            continue
        unknown.append("외부 송금 뒤 장부 갱신의 재진입/rollback 관계 미지원")
    if any(any(other != lock for other in payout_locks) for lock in late_reset_locks):
        unknown.append("사후 장부 초기화의 잠금을 공유하지 않는 다른 출금 진입점이 있어 교차 함수 재진입 검토가 필요합니다.")
    if unknown:
        # Unknown payable paths must never justify the no-user-deposit boundary.
        raise Unsupported("; ".join(dict.fromkeys(unknown)))
    if not deposits:
        return result("BENIGN", "지원 범위에 ETH 예치/수신 경로가 없고 예치 장부는 0에서 시작합니다. "
                      "다른 사용자 자산 경로도 없습니다. 강제 송금된 ETH를 사용자 자산으로 보지 않는 대회 가정에 따라 "
                      "소유자 회수/임의 실행만으로 탈취로 분류하지 않습니다. 일반 프로젝트의 보편적 안전 보장은 아닙니다.", sweeps + executions + withdrawals)
    if executions:
        return result("MALICIOUS", "사용자 ETH 예치와 소유자 제어 대상·데이터의 delegatecall이 연결됩니다. "
                      "선택한 코드는 이 금고의 저장소·자산 문맥에서 실행되어 예치 기록이나 자산을 변경할 수 있습니다.", deposits + executions)
    if sweeps:
        return result("MALICIOUS", "사용자 ETH가 예치되지만 소유자는 사용자별 예치 권리/차감과 무관하게 "
                      "금고 전체 ETH를 소유자 주소로 송금할 수 있습니다.", deposits + sweeps)
    if reentry:
        return result("MALICIOUS", "자기 예치 잔액을 읽어 송금한 뒤 장부를 0으로 만듭니다. "
                      "외부 수령자가 호출을 돌려주기 전에 같은 출금에 재진입하면 아직 남은 장부로 다시 지급받을 수 있습니다. "
                      "후속 처리는 checked 차감이 아닌 0 대입이므로 중복 지급을 underflow로 취소하지 않습니다. "
                      "다른 사용자의 예치금까지 금고에 있을 때 자신의 예치액을 넘는 지급 경로입니다.", deposits + reentry)
    return result("BENIGN", "사용자 입금은 본인의 예치 장부에 더해지고, 모든 송금은 본인에게 지급되며 동일 금액을 본인 장부에 반영합니다. "
                  "경로별로 선행 차감/초기화, 실행 중 잠금, 또는 성공한 모든 지급분의 checked 차감을 확인했습니다. "
                  "이 단일 장부 범위에서 예치액 초과 지급은 차단/거래 취소되며 다른 자산 이동 경로는 없습니다.", deposits + withdrawals)
