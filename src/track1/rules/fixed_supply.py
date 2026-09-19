"""생성자 발행 후 직접 전송/승인/한도 내 대리 전송만 있는 정상 경계."""
from slither.core.solidity_types.mapping_type import MappingType

from .common import read_contract, runtime, constructor_trace, check_declarations
from .linear import SENDER, Unsupported, symbol
from .supply import evidence, index, is_parameter, transfer_balance, zero_check
from ..reporting import explain


def allowance_type(variable):
    kind = variable.type
    return (isinstance(kind, MappingType) and str(kind.type_from) == "address"
            and isinstance(kind.type_to, MappingType) and str(kind.type_to.type_from) == "address"
            and str(kind.type_to.type_to) == "uint256")


def approve_shape(function, trace):
    if function.modifiers or len(trace.writes) != 1:
        return None
    location, amount, _ = trace.writes[0]
    if (location[0] != "index" or location[1][0] != "index"
            or location[1][1][0] != "variable" or location[1][2] != SENDER):
        return None
    allowance = location[1][1][1]
    spender = location[2]
    if (not allowance_type(allowance) or not is_parameter(spender, function, "address")
            or not is_parameter(amount, function, "uint256")
            or not all(zero_check(g, spender) for g, _ in trace.guards)):
        return None
    return allowance


def delegated_shape(function, trace, balance, allowance):
    if function.modifiers or len(trace.writes) != 3:
        return False
    (permission, decrement, _), (debit, sub, _), (credit, add, _) = trace.writes
    if debit[0] != "index" or credit[0] != "index" or sub[0] != "SUBTRACTION":
        return False
    origin, recipient, amount = debit[2], credit[2], sub[2]
    if not (is_parameter(origin, function, "address") and is_parameter(recipient, function, "address")
            and is_parameter(amount, function, "uint256")):
        return False
    expected_permission = ("index", index(allowance, origin), SENDER)
    if (permission != expected_permission or decrement != ("SUBTRACTION", permission, amount)
            or debit != index(balance, origin) or sub != ("SUBTRACTION", debit, amount)
            or credit != index(balance, recipient) or add != ("ADDITION", credit, amount)):
        return False
    required = {("GREATER_EQUAL", permission, amount), ("GREATER_EQUAL", debit, amount)}
    guards = {g for g, _ in trace.guards}
    return required <= guards and all(g in required or zero_check(g, recipient) for g in guards)


def analyze_contract(contract):
    traces = read_contract(contract)
    functions = runtime(traces)
    transfers = {f: transfer_balance(f, t) for f, t in functions}
    balances = {b for b in transfers.values() if b is not None}
    if len(balances) != 1:
        raise Unsupported("기본 잔액 전송 구조를 식별하지 못했습니다.")
    balance = balances.pop()
    approvals = {f: approve_shape(f, t) for f, t in functions if transfers[f] is None}
    allowances = {a for a in approvals.values() if a is not None}
    if len(allowances) > 1:
        raise Unsupported("복수 승인 저장소는 지원하지 않습니다.")
    allowance = next(iter(allowances), None)
    for function, trace in functions:
        if transfers[function] is not None or approvals.get(function) is not None:
            continue
        if allowance is None or not delegated_shape(function, trace, balance, allowance):
            raise Unsupported("승인 한도/잔액 차감으로 설명하지 못한 실행 경로가 있습니다.")
    constructor, initial = constructor_trace(traces)
    if len(initial.writes) != 2:
        raise Unsupported("초기 공급량과 잔액의 두 대입을 확인하지 못했습니다.")
    (supply, quantity, supply_node), (credit, balance_quantity, _) = initial.writes
    if (supply[0] != "variable" or str(supply[1].type) != "uint256"
            or not is_parameter(quantity, constructor, "uint256")
            or credit != index(balance, SENDER) or balance_quantity != quantity):
        raise Unsupported("생성자의 초기 공급량/호출자 잔액을 연결하지 못했습니다.")
    check_declarations(traces, {supply[1], balance, allowance})
    return explain({"verdict": "BENIGN", "reasons": [
        "공급량은 생성자에서만 설정되고 이후 증가/감소 경로가 없습니다. 모든 실행 경로는 "
        "호출자 잔액의 동일량 전송, 호출자가 자기 승인 한도를 설정하는 대입, "
        "또는 잔액과 호출자 승인 한도를 검사·차감하는 대리 전송 범위에 있습니다. "
        "추가 상태 변경이나 외부 호출은 확인되지 않았습니다."],
        "evidence": [evidence(constructor, supply_node)]}, list(traces.items()))
