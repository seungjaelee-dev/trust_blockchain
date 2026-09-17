"""각 규칙이 공유하는 제한된 컨트랙트 범위/초기화 검사."""
from .linear import Unsupported, trace_function


def read_contract(contract, allow_calls=False):
    if contract.inheritance or contract.is_abstract or not contract.is_fully_implemented:
        raise Unsupported("상속/추상/미완성 컨트랙트는 지원하지 않습니다.")
    traces = {}
    for function in contract.functions:
        if not function.is_constructor_variables and not function.is_implemented:
            raise Unsupported("구현 없는 함수는 지원하지 않습니다.")
        if function.payable and not allow_calls:
            raise Unsupported("토큰 규칙은 payable 함수를 지원하지 않습니다.")
        if not function.is_constructor and not function.is_constructor_variables and function.visibility not in {"public", "external"}:
            raise Unsupported("내부 함수는 지원하지 않습니다.")
        traces[function] = trace_function(function, allow_calls=allow_calls)
    return traces


def runtime(traces):
    return [(f, t) for f, t in traces.items() if not f.is_constructor and not f.is_constructor_variables]


def constructor_trace(traces):
    constructors = [(f, t) for f, t in traces.items() if f.is_constructor]
    if len(constructors) != 1:
        raise Unsupported("단일 생성자를 확인하지 못했습니다.")
    function, trace = constructors[0]
    if function.payable or trace.guards or trace.calls:
        raise Unsupported("생성자의 예치/조건/호출은 지원하지 않습니다.")
    return function, trace


def check_declarations(traces, roles):
    for function, trace in traces.items():
        if function.is_constructor_variables:
            if trace.guards or trace.calls:
                raise Unsupported("선언부의 조건/호출은 지원하지 않습니다.")
            for location, value, _ in trace.writes:
                if location[0] != "variable" or location[1] in roles or value[0] != "constant":
                    raise Unsupported("역할 상태의 선언부 초기화 또는 복잡한 초기값은 지원하지 않습니다.")
