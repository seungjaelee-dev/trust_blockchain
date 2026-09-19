"""직접 예치와 소유자 제어 delegatecall의 결합. 일반 proxy 판정기는 아니다."""
from .common import read_contract, runtime, constructor_trace, check_declarations
from .linear import SENDER, VALUE, Unsupported, symbol
from .supply import evidence, equal, index, is_balance, is_parameter
from ..reporting import explain


def analyze_contract(contract):
    traces = read_contract(contract, allow_calls=True)
    constructor, initial = constructor_trace(traces)
    if len(initial.writes) != 1:
        raise Unsupported("단일 소유자 초기화를 확인하지 못했습니다.")
    owner, sender, _ = initial.writes[0]
    if owner[0] != "variable" or str(owner[1].type) != "address" or sender != SENDER:
        raise Unsupported("소유자가 생성자 호출자로 초기화되지 않았습니다.")
    deposits, executions, withdrawals = [], [], []
    for function, trace in runtime(traces):
        if function.payable and not trace.guards and not trace.calls and len(trace.writes) == 1:
            location, addition, node = trace.writes[0]
            if (location[0] == "index" and location[1][0] == "variable"
                    and is_balance(location[1][1]) and location[2] == SENDER
                    and addition == ("ADDITION", location, VALUE)):
                deposits.append((location[1][1], evidence(function, node)))
                continue
        if function.payable or len(trace.calls) != 1:
            raise Unsupported("직접 예치/임의 실행/기본 출금 이외의 경로는 지원하지 않습니다.")
        call = trace.calls[0]
        conditions = [g for g, _ in trace.guards]
        success = ("call_success", 0)
        if success not in conditions:
            raise Unsupported("외부 호출 성공 확인을 연결하지 못했습니다.")
        before = [g for g in conditions if g != success]
        if (call["kind"] == "delegatecall" and not trace.writes and call["value"] is None
                and is_parameter(call["destination"], function, "address")
                and len(call["arguments"]) == 1 and is_parameter(call["arguments"][0], function, "bytes")
                and before and all(equal(g, SENDER, owner) for g in before)):
            executions.append(evidence(function, call["node"]))
            continue
        if call["kind"] == "call" and call["destination"] == SENDER and len(trace.writes) == 1:
            location, subtraction, _ = trace.writes[0]
            quantity = call["value"]
            if (location[0] == "index" and location[1][0] == "variable" and location[2] == SENDER
                    and quantity is not None and is_parameter(quantity, function, "uint256")
                    and subtraction == ("SUBTRACTION", location, quantity)
                    and before == [("GREATER_EQUAL", location, quantity)]
                    and all(a[0] == "constant" and a[2] == "" for a in call["arguments"])):
                withdrawals.append(location[1][1])
                continue
        raise Unsupported("호출 권한/대상/데이터/출금 관계를 지원 범위에서 확인하지 못했습니다.")
    ledgers = {variable for variable, _ in deposits}
    if len(ledgers) != 1 or not executions:
        raise Unsupported("사용자 예치 경로와 임의 delegatecall을 함께 확인하지 못했습니다.")
    ledger = ledgers.pop()
    if any(variable != ledger for variable in withdrawals):
        raise Unsupported("예치와 출금의 저장소가 일치하지 않습니다.")
    check_declarations(traces, {owner[1], ledger})
    return explain({"verdict": "MALICIOUS", "reasons": [
        "사용자는 payable 경로로 ETH를 예치하며 msg.value가 호출자의 예치 기록에 더해집니다. "
        "생성자에서 설정된 소유자는 대상 주소와 bytes 데이터를 직접 선택하여 delegatecall을 실행할 수 있습니다. "
        "선택된 코드는 이 컨트랙트의 저장소와 자산 문맥에서 실행되므로 예치 기록 변경이나 자산 이동에 "
        "사용될 수 있습니다."],
        "evidence": [item for _, item in deposits] + executions}, list(traces.items()), kind="delegatecall")
