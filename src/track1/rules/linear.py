"""규칙 공통의 제한된 IR 해석. 분기/호출을 추측하지 않고 미지원이면 중단한다.

식의 v 항목은 문자열 이름이 아닌 Slither 변수 선언 객체를 보관한다.
CFG의 sons를 따라가며 입력값, 검사식, 상태 쓰기를 연결한다.
"""
from dataclasses import dataclass, field

from slither.core.cfg.node import NodeType
from slither.core.declarations import Modifier, SolidityVariableComposed
from slither.core.variables.state_variable import StateVariable
from slither.core.variables.local_variable import LocalVariable
from slither.slithir.operations import (
    Assignment, Binary, EventCall, Index, InternalCall, Return, SolidityCall, TypeConversion,
    LowLevelCall, Unpack,
)
from slither.slithir.operations.binary import BinaryType
from slither.slithir.variables import Constant
from .checked import validate_checked


class Unsupported(Exception):
    """해당 경로가 현재 증명 범위를 벗어남."""

    def __init__(self, message, node=None):
        super().__init__(message)
        self.node = node


SENDER = ("builtin", "msg.sender")
VALUE = ("builtin", "msg.value")
ZERO_ADDRESS = ("constant", "address", 0)


def symbol(variable):
    return ("variable", variable)


@dataclass
class Trace:
    guards: list = field(default_factory=list)  # (조건식, 원본 노드)
    writes: list = field(default_factory=list)  # (저장 위치, 새 값, 원본 노드)
    calls: list = field(default_factory=list)  # 별도 delegatecall 규칙만 사용
    checked: list = field(default_factory=list)


def linear_nodes(function):
    node = function.entry_point
    visited = set()
    while node is not None:
        if node in visited or len(node.sons) > 1:
            raise Unsupported("분기 또는 반복 경로는 현재 선형 분석에서 지원하지 않습니다.")
        visited.add(node)
        if node.type not in {
            NodeType.ENTRYPOINT, NodeType.OTHER_ENTRYPOINT, NodeType.EXPRESSION,
            NodeType.VARIABLE, NodeType.RETURN, NodeType.PLACEHOLDER,
        }:
            raise Unsupported(f"지원하지 않는 노드 종류: {node.type.name}.")
        yield node
        node = node.sons[0] if node.sons else None


def trace_function(function, modifier=False, allow_calls=False):
    trace = Trace()
    values, references, storage = {}, {}, {}
    placeholders = 0

    def read(variable):
        if isinstance(variable, Constant):
            return ("constant", str(variable.type), variable.value)
        if isinstance(variable, SolidityVariableComposed) and variable.name in {"msg.sender", "msg.value"}:
            return ("builtin", variable.name)
        if variable in references:
            location = references[variable]
            return storage.get(location, location)
        if variable in values:
            return values[variable]
        if isinstance(variable, (StateVariable, LocalVariable)):
            location = symbol(variable)
            return storage.get(location, location)
        raise Unsupported("입력값의 유래를 해석하지 못했습니다.")

    def write(variable, expression, node):
        if trace.calls:
            raise Unsupported("외부 호출 이후 대입/상태 쓰기는 지원하지 않습니다.")
        if isinstance(variable, StateVariable) or variable in references:
            location = references[variable] if variable in references else symbol(variable)
            storage[location] = expression
            trace.writes.append((location, expression, node))
        else:
            values[variable] = expression

    for node in linear_nodes(function):
        if node.type == NodeType.PLACEHOLDER:
            placeholders += 1
            if not modifier:
                raise Unsupported("함수 안의 modifier placeholder를 해석하지 못했습니다.")
        for operation in node.irs:
            if placeholders:
                raise Unsupported("modifier 본문 실행 이후의 연산 또는 복수 _ 는 지원하지 않습니다.")
            if isinstance(operation, Index):
                base = operation.variable_left
                if isinstance(base, StateVariable):
                    location = symbol(base)
                elif base in references:
                    location = references[base]
                else:
                    raise Unsupported("저장소 인덱스의 선언 연결을 지원하지 않습니다.")
                references[operation.lvalue] = ("index", location, read(operation.variable_right))
            elif isinstance(operation, Assignment):
                write(operation.lvalue, read(operation.rvalue), node)
            elif isinstance(operation, Binary):
                if operation.type not in {
                    BinaryType.ADDITION, BinaryType.SUBTRACTION, BinaryType.EQUAL,
                    BinaryType.NOT_EQUAL, BinaryType.LESS_EQUAL, BinaryType.GREATER_EQUAL,
                }:
                    raise Unsupported(f"지원하지 않는 연산: {operation.type.name}.")
                if operation.type in {BinaryType.ADDITION, BinaryType.SUBTRACTION} and not node.scope.is_checked:
                    raise Unsupported("unchecked 산술은 지원하지 않습니다.")
                expression = (operation.type.name, read(operation.variable_left), read(operation.variable_right))
                if operation.type in {BinaryType.ADDITION, BinaryType.SUBTRACTION}:
                    trace.checked.append((expression, node))
                write(operation.lvalue, expression, node)
            elif isinstance(operation, TypeConversion):
                original = read(operation.variable)
                if str(operation.type) != "address" or original != ("constant", "uint256", 0):
                    raise Unsupported("영 주소 이외의 타입 변환은 지원하지 않습니다.")
                values[operation.lvalue] = ZERO_ADDRESS
            elif isinstance(operation, SolidityCall):
                # 내장 함수의 실제 의미를 사용한다. 사용자 정의 함수명 매칭이 아니다.
                if operation.function.name not in {"require(bool)", "require(bool,string)"}:
                    raise Unsupported("require 이외의 내장 호출은 지원하지 않습니다.")
                condition = read(operation.arguments[0])
                if trace.calls:
                    if condition != ("call_success", len(trace.calls) - 1):
                        raise Unsupported("외부 호출 뒤 성공 확인 이외의 조건은 지원하지 않습니다.")
                elif trace.writes:
                    raise Unsupported("상태 변경 이후 검사식은 이번 버전에서 지원하지 않습니다.")
                trace.guards.append((condition, node))
            elif isinstance(operation, InternalCall):
                if modifier or not isinstance(operation.function, Modifier) or operation.arguments:
                    raise Unsupported("내부 호출/인자 있는 modifier는 지원하지 않습니다.")
                if trace.writes or trace.calls:
                    raise Unsupported("상태 변경 이후 modifier 호출은 지원하지 않습니다.")
                nested = trace_function(operation.function, modifier=True)
                trace.guards.extend(nested.guards)
            elif isinstance(operation, EventCall):
                pass  # 이벤트 이름/내용은 판정에 사용하지 않는다.
            elif isinstance(operation, LowLevelCall) and allow_calls and not modifier:
                if trace.calls or operation.call_gas is not None:
                    raise Unsupported("복수 외부 호출/지정 gas는 지원하지 않습니다.")
                call_id = len(trace.calls)
                trace.calls.append({"kind": operation.function_name.value,
                                    "destination": read(operation.destination),
                                    "arguments": [read(a) for a in operation.arguments],
                                    "value": read(operation.call_value) if operation.call_value is not None else None,
                                    "node": node})
                values[operation.lvalue] = ("call_result", call_id)
            elif isinstance(operation, Unpack) and allow_calls:
                result = read(operation.tuple)
                if result[0] != "call_result" or operation.index != 0:
                    raise Unsupported("외부 호출 성공 여부 이외의 반환값은 지원하지 않습니다.")
                values[operation.lvalue] = ("call_success", result[1])
            elif isinstance(operation, Return):
                if [read(value) for value in operation.values] != [("constant", "bool", True)]:
                    raise Unsupported("true 이외의 반환값은 지원하지 않습니다.")
            else:
                raise Unsupported(f"지원하지 않는 IR 연산: {type(operation).__name__}.")
    if modifier and (placeholders != 1 or trace.writes):
        raise Unsupported("modifier가 단일 _ 이전의 검사만 수행하지 않습니다.")
    limitation = validate_checked(trace.checked, trace.guards, trace.writes)
    if limitation:
        raise Unsupported(limitation)
    return trace
