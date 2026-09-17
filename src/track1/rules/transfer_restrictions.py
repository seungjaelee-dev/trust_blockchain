"""소유자 초기 허용 + 소유자 목록 관리 + 발신자 제한의 연결."""
from dataclasses import replace
from slither.core.solidity_types.mapping_type import MappingType
from slither.core.variables.state_variable import StateVariable

from .common import read_contract, runtime, constructor_trace, check_declarations
from .linear import SENDER, Unsupported, symbol
from .supply import evidence, equal, index, is_parameter, transfer_balance


def analyze_contract(contract):
    traces = read_contract(contract)
    constructor, initial = constructor_trace(traces)
    if len(initial.writes) != 4:
        raise Unsupported("소유자/공급량/잔액/허용목록 초기화를 확인하지 못했습니다.")
    (owner, sender, _), (supply, amount, _), (credit, credit_amount, _), (allowed, enabled, init_node) = initial.writes
    if (owner[0] != "variable" or not isinstance(owner[1], StateVariable) or str(owner[1].type) != "address"
            or sender != SENDER or supply[0] != "variable" or str(supply[1].type) != "uint256"
            or not is_parameter(amount, constructor, "uint256") or credit_amount != amount
            or credit[0] != "index" or credit[1][0] != "variable" or credit[2] != SENDER
            or allowed[0] != "index" or allowed[1][0] != "variable" or allowed[2] != SENDER
            or enabled != ("constant", "bool", True)):
        raise Unsupported("생성자의 소유자 초기 허용과 초기 자산 관계를 확인하지 못했습니다.")
    balance, allowlist = credit[1][1], allowed[1][1]
    kind = allowlist.type
    if not isinstance(kind, MappingType) or str(kind.type_from) != "address" or str(kind.type_to) != "bool":
        raise Unsupported("주소별 허용 상태 저장소를 식별하지 못했습니다.")
    check_declarations(traces, {owner[1], supply[1], balance, allowlist})
    transfers, setters = [], []
    for function, trace in runtime(traces):
        restriction = index(allowlist, SENDER)
        guards = [(g, n) for g, n in trace.guards if g != restriction]
        filtered = replace(trace, guards=guards)
        if len(guards) < len(trace.guards) and transfer_balance(function, filtered) == balance:
            transfers.append(evidence(function, next(n for g, n in trace.guards if g == restriction)))
            continue
        if len(trace.writes) == 1 and trace.guards and all(equal(g, SENDER, owner) for g, _ in trace.guards):
            location, value, node = trace.writes[0]
            if (location[0] == "index" and location[1] == symbol(allowlist)
                    and is_parameter(location[2], function, "address") and is_parameter(value, function, "bool")):
                setters.append(evidence(function, node))
                continue
        raise Unsupported("제한 전송/소유자 목록 관리 이외의 경로가 있어 비대칭성을 확정하지 못했습니다.")
    if not transfers or not setters:
        raise Unsupported("발신자 제한과 소유자 전용 목록 변경을 함께 확인하지 못했습니다.")
    return {"verdict": "MALICIOUS", "reasons": [
        "전송은 발신자의 주소별 허용 상태를 요구합니다. 생성자에서 소유자만 초기 허용되며, "
        "소유자는 수령자의 허용 여부와 무관하게 토큰을 보낼 수 있습니다. 목록 변경도 "
        "소유자만 수행하므로 일반 수령자는 허용되지 않으면 받은 토큰을 다시 전송할 수 없습니다."],
        "evidence": [evidence(constructor, init_node), *setters, *transfers]}
