"""R1: 직접 발행과 기본 잔액 전송만 있는 작은 컨트랙트의 공급량 경계.

이름/주석을 읽지 않는다. 전송의 차감/증가 관계로 잔액 mapping을 식별하고,
동일 입력값의 scalar/mapping 증가를 발행으로 연결한다. 나머지 함수가 미지원이면
파일 전체의 안전을 주장하지 않는다. 전체 Solidity를 위한 증명기가 아니다.
"""
from slither.core.solidity_types.mapping_type import MappingType
from slither.core.variables.state_variable import StateVariable

from .linear import SENDER, ZERO_ADDRESS, Unsupported, symbol, trace_function
from ..reporting import explain


def evidence(function, node):
    return {"function": function.full_name, "line": min(node.source_mapping.lines)}


def is_parameter(expression, function, kind):
    return (expression[0] == "variable" and expression[1] in function.parameters
            and str(expression[1].type) == kind)


def is_balance(variable):
    return (isinstance(variable, StateVariable) and isinstance(variable.type, MappingType)
            and str(variable.type.type_from) == "address"
            and str(variable.type.type_to) == "uint256")


def index(variable, key):
    return ("index", symbol(variable), key)


def equal(expression, left, right):
    return expression in (("EQUAL", left, right), ("EQUAL", right, left))


def zero_check(expression, recipient):
    return expression in (("NOT_EQUAL", recipient, ZERO_ADDRESS),
                          ("NOT_EQUAL", ZERO_ADDRESS, recipient))


def transfer_balance(function, trace):
    """호출자 잔액 차감과 수령자 동일량 증가의 관계를 검사한다."""
    if len(trace.writes) != 2 or function.modifiers:
        return None
    (debit, sub, _), (credit, add, _) = trace.writes
    if debit[0] != "index" or credit[0] != "index" or debit[1] != credit[1]:
        return None
    balance = debit[1][1]
    if not is_balance(balance) or debit[2] != SENDER or not is_parameter(credit[2], function, "address"):
        return None
    if sub[0] != "SUBTRACTION" or sub[1] != debit or not is_parameter(sub[2], function, "uint256"):
        return None
    amount = sub[2]
    if add != ("ADDITION", credit, amount):
        return None
    sufficient = ("GREATER_EQUAL", debit, amount)
    guards = [condition for condition, _ in trace.guards]
    if sufficient not in guards or not all(g == sufficient or zero_check(g, credit[2]) for g in guards):
        return None
    return balance


def mint_shape(function, trace, balance):
    if len(trace.writes) != 2:
        raise Unsupported("발행/기본 전송으로 설명하지 못한 상태 쓰기가 있습니다.")
    (location, addition, write_node), (destination, credit, _) = trace.writes
    if location[0] != "variable" or str(location[1].type) != "uint256":
        raise Unsupported("공급량 상태값을 식별하지 못했습니다.")
    if addition[0] != "ADDITION" or addition[1] != location or not is_parameter(addition[2], function, "uint256"):
        raise Unsupported("공급량 증가량이 직접 입력값에 연결되지 않습니다.")
    amount = addition[2]
    if destination[0] != "index" or destination[1] != symbol(balance) or credit != ("ADDITION", destination, amount):
        raise Unsupported("공급량 증가와 동일한 잔액 증가를 연결하지 못했습니다.")
    recipient = destination[2]
    owner = None
    for condition, _ in trace.guards:
        if condition[0] == "EQUAL":
            for candidate in condition[1:]:
                if (candidate[0] == "variable" and isinstance(candidate[1], StateVariable)
                        and str(candidate[1].type) == "address" and equal(condition, SENDER, candidate)):
                    owner = candidate[1]
    if owner is None:
        raise Unsupported("초기 소유자와 연결할 호출자 제한을 확인하지 못했습니다.")
    if recipient != symbol(owner) and not is_parameter(recipient, function, "address"):
        raise Unsupported("발행 수령자의 값 유래를 지원하지 않습니다.")
    caps, cap_nodes = [], []
    for condition, node in trace.guards:
        if equal(condition, SENDER, symbol(owner)) or zero_check(condition, recipient):
            continue
        if condition[0] == "LESS_EQUAL" and condition[1] == addition:
            cap = condition[2]
            if cap[0] == "variable" and isinstance(cap[1], StateVariable) and cap[1].is_constant:
                caps.append(cap[1])
                cap_nodes.append(node)
                continue
        raise Unsupported("발행 검사식의 효력/증가량 연결을 확인하지 못했습니다.")
    return {"function": function, "supply": location[1], "owner": owner,
            "caps": caps, "node": write_node, "cap_nodes": cap_nodes}


def check_initialization(contract, traces, supply, owner, balance, capped):
    """소유자 초기화, 상수 상한, 생성자 공급량/잔액의 연결을 확인한다."""
    constants = {}
    constructor = None
    for function, trace in traces.items():
        if function.is_constructor_variables:
            if trace.guards:
                raise Unsupported("상태 초기화의 조건을 지원하지 않습니다.")
            for location, value, _ in trace.writes:
                if location[0] != "variable" or value[0] != "constant":
                    raise Unsupported("상태 초기화가 단순 상수 대입이 아닙니다.")
                variable = location[1]
                if variable in {supply, owner, balance}:
                    raise Unsupported("역할 상태변수의 선언부 초기화는 지원하지 않습니다.")
                constants[variable] = value
        elif function.is_constructor:
            constructor = (function, trace)
    if constructor is None:
        raise Unsupported("소유자 생성자 초기화를 확인하지 못했습니다.")
    function, trace = constructor
    writes = [(location, value) for location, value, _ in trace.writes]
    if trace.guards or not writes or writes[0] != (symbol(owner), SENDER):
        raise Unsupported("생성자의 소유자 초기화/조건을 지원하지 않습니다.")
    if len(writes) != 1:
        # 초기 발행은 반복 호출 가능한 발행으로 취급하지 않는다.
        if capped or len(writes) != 3:
            raise Unsupported("상한 있는 컨트랙트의 초기 공급량 또는 추가 생성자 쓰기를 검증하지 못했습니다.")
        initial = writes[1][1]
        if (writes[1][0] != symbol(supply) or not is_parameter(initial, function, "uint256")
                or writes[2] != (index(balance, SENDER), initial)):
            raise Unsupported("생성자의 초기 공급량/잔액 연결을 확인하지 못했습니다.")
    return constants


def analyze_contract(contract):
    if contract.is_abstract or not contract.is_fully_implemented:
        raise Unsupported("배포할 수 없는 추상/미완성 컨트랙트는 지원하지 않습니다.")
    if contract.inheritance:
        raise Unsupported("상속 관계는 R1 첫 버전에서 지원하지 않습니다.")
    traces = {}
    for function in contract.functions:
        if function.payable or (not function.is_implemented and not function.is_constructor_variables):
            raise Unsupported("payable 또는 구현 없는 함수는 지원하지 않습니다.")
        if not function.is_constructor and not function.is_constructor_variables and function.visibility not in {"public", "external"}:
            raise Unsupported("내부 함수가 있는 컨트랙트는 지원하지 않습니다.")
        traces[function] = trace_function(function)
    runtime = [(f, t) for f, t in traces.items() if not f.is_constructor and not f.is_constructor_variables]
    transfers = {f: transfer_balance(f, t) for f, t in runtime}
    balances = {balance for balance in transfers.values() if balance is not None}
    if len(balances) != 1:
        raise Unsupported("호출자 잔액 차감/수령자 동일량 증가로 잔액 저장소를 식별하지 못했습니다.")
    balance = balances.pop()
    mints = [mint_shape(f, t, balance) for f, t in runtime if transfers[f] is None]
    if not mints:
        raise Unsupported("직접 발행 경로가 없어 이번 R1 판정 범위에 해당하지 않습니다.")
    supplies, owners = {m["supply"] for m in mints}, {m["owner"] for m in mints}
    if len(supplies) != 1 or len(owners) != 1:
        raise Unsupported("발행 경로들의 공급량/소유자가 일치하지 않습니다.")
    supply, owner = supplies.pop(), owners.pop()
    constants = check_initialization(contract, traces, supply, owner, balance, any(m["caps"] for m in mints))
    for mint in mints:
        for cap in mint["caps"]:
            value = constants.get(cap)
            if value is None or value[:2] != ("constant", "uint256") or not 0 < value[2] < 2**256 - 1:
                raise Unsupported("고정된 유효 공급량 상한값을 확인하지 못했습니다.")
    unbounded = [mint for mint in mints if not mint["caps"]]
    if unbounded:
        return explain({
            "verdict": "MALICIOUS",
            "reasons": ["생성자에서 지정된 소유자가 외부 발행 함수를 반복 호출할 수 있습니다. "
                        "입력 증가량이 공급량과 전송 가능한 주소별 잔액에 동일하게 더해지며, "
                        "해당 직접 경로에 공급량 상한 검사가 없어 보유자 지분을 희석할 수 있습니다. "
                        "정수 overflow 제한은 경제적 공급량 상한으로 취급하지 않았습니다."],
            "evidence": [evidence(m["function"], m["node"]) for m in unbounded],
        }, list(traces.items()), kind="unbounded_mint")
    return explain({
        "verdict": "BENIGN",
        "reasons": ["지원 범위의 모든 외부 상태 변경 경로를 확인했습니다. 초기 공급량은 0이며, "
                    "모든 발행은 동일한 실제 증가량을 더한 공급량이 변경 불가능한 상수 상한 이하인지 "
                    "검사한 뒤 실행됩니다. 나머지 상태 변경은 호출자의 잔액 차감과 수령자의 동일량 증가입니다. "
                    "외부 호출·추가 상태 쓰기는 없으며, 소유자의 상한 내 발행 권한은 중앙화 위험으로 남습니다."],
        "evidence": [evidence(m["function"], n) for m in mints for n in m["cap_nodes"]],
    }, list(traces.items()))
