"""Bounded, acyclic SlithIR paths. No source text/name matching.

This is a deliberately small interpreter, not a complete EVM. Unknown operations,
loops, recursive calls and unsupported modifier layouts fail closed. State writes
and guards retain execution order; a later require constrains transaction success.
"""
from dataclasses import dataclass, field
from slither.core.cfg.node import NodeType
from slither.core.declarations import Modifier, SolidityVariable, SolidityVariableComposed
from slither.core.variables.state_variable import StateVariable
from slither.core.variables.local_variable import LocalVariable
from slither.slithir.operations import (Assignment, Binary, Condition, Unary, EventCall,
    Index, InternalCall, Return, SolidityCall, TypeConversion, LowLevelCall, Unpack)
from slither.slithir.variables import Constant
from .linear import SENDER, VALUE, ZERO_ADDRESS, Unsupported, symbol
from .checked import validate_checked

MAX_PATHS = 64
MAX_DEPTH = 8
MAX_NODES = 400
UINT_MAX = 2**256 - 1
TRUE = ("constant", "bool", True)
FALSE = ("constant", "bool", False)
ZERO = ("constant", "uint256", 0)
THIS = ("builtin", "this")
ETHER = ("builtin", "ether_balance")


def negate(expr):
    if expr == TRUE:
        return FALSE
    if expr == FALSE:
        return TRUE
    if expr[0] == "NOT":
        return expr[1]
    inverse = {"LESS": "GREATER_EQUAL", "GREATER": "LESS_EQUAL",
               "LESS_EQUAL": "GREATER", "GREATER_EQUAL": "LESS",
               "EQUAL": "NOT_EQUAL", "NOT_EQUAL": "EQUAL"}
    return simplify(inverse[expr[0]], *expr[1:]) if expr[0] in inverse else ("NOT", expr)


def flatten(expr):
    if expr[0] == "ANDAND":
        return flatten(expr[1]) + flatten(expr[2])
    return [expr]


def simplify(op, left, right):
    if op == "GREATER_EQUAL":
        return ("LESS_EQUAL", right, left)
    if op == "GREATER":
        return ("LESS", right, left)
    if left[0] == right[0] == "constant":
        a, b = left[2], right[2]
        operations = {"EQUAL": lambda: a == b, "NOT_EQUAL": lambda: a != b,
                      "LESS": lambda: a < b, "LESS_EQUAL": lambda: a <= b,
                      "ANDAND": lambda: a and b, "OROR": lambda: a or b}
        if op in operations:
            return TRUE if operations[op]() else FALSE
    return (op, left, right)


@dataclass
class Path:
    guards: list = field(default_factory=list)
    writes: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    checked: list = field(default_factory=list)
    values: dict = field(default_factory=dict)
    refs: dict = field(default_factory=dict)
    storage: dict = field(default_factory=dict)
    result: tuple = ()
    stopped: bool = False

    def clone(self):
        return Path(list(self.guards), list(self.writes), list(self.calls), list(self.steps),
                    list(self.checked), dict(self.values), dict(self.refs), dict(self.storage),
                    self.result, self.stopped)

    def read(self, variable):
        if isinstance(variable, Constant):
            return ("constant", str(variable.type), variable.value)
        if isinstance(variable, (SolidityVariableComposed, SolidityVariable)):
            known = {"msg.sender": SENDER, "msg.value": VALUE, "this": THIS}
            if variable.name in known:
                return known[variable.name]
            raise Unsupported("지원하지 않는 Solidity 내장 값입니다.")
        if variable in self.refs:
            loc = self.refs[variable]
            return self.storage.get(loc, loc)
        if variable in self.values:
            return self.values[variable]
        if isinstance(variable, (StateVariable, LocalVariable)):
            loc = symbol(variable)
            return self.storage.get(loc, loc)
        raise Unsupported("경로 분석에서 값의 선언 연결을 읽지 못했습니다.")

    def write(self, variable, value, node):
        if isinstance(variable, StateVariable) or variable in self.refs:
            loc = self.refs.get(variable, symbol(variable))
            self.storage[loc] = value
            self.writes.append((loc, value, node))
            self.steps.append(("write", loc, value, node))
        else:
            self.values[variable] = value

    def guard(self, expr, node):
        for condition in flatten(expr):
            if condition == FALSE or any(negate(g) == condition for g, _ in self.guards):
                return False
            if condition != TRUE:
                self.guards.append((condition, node))
                self.steps.append(("guard", condition, node))
        return True


def trace_paths(function, seed=None, stack=()):
    if function in stack or len(stack) >= MAX_DEPTH:
        raise Unsupported("재귀 호출 또는 내부 호출 깊이 제한입니다.")
    stack = (*stack, function)
    if isinstance(function, Modifier):
        placeholders = [n for n in function.nodes if n.type == NodeType.PLACEHOLDER]
        if len(placeholders) != 1:
            raise Unsupported("modifier는 본문 실행 위치 _ 가 정확히 하나여야 합니다.")
    queue = [(function.entry_point, seed or Path(), frozenset())]
    completed = []
    visited_count = 0
    while queue:
        if len(queue) + len(completed) > MAX_PATHS:
            raise Unsupported("분기 경로 수 제한을 초과했습니다.")
        node, path, visited = queue.pop()
        if node is None or path.stopped:
            if isinstance(function, Modifier):
                raise Unsupported("본문 _ 에 도달하지 않는 modifier 경로는 미지원입니다.")
            completed.append(path)
            continue
        visited_count += 1
        if node in visited or visited_count > MAX_NODES:
            raise Unsupported("반복 경로 또는 노드 예산 초과입니다.")
        visited = visited | {node}
        if node.type == NodeType.PLACEHOLDER:
            # Only precondition modifiers. Post-body effects require explicit wrapping.
            if not isinstance(function, Modifier) or node.sons:
                raise Unsupported("본문 뒤 동작이 있는 modifier는 지원하지 않습니다.")
            completed.append(path)
            continue
        if node.type not in {NodeType.ENTRYPOINT, NodeType.OTHER_ENTRYPOINT,
                NodeType.EXPRESSION, NodeType.VARIABLE, NodeType.RETURN,
                NodeType.IF, NodeType.ENDIF, NodeType.THROW}:
            raise Unsupported(f"미지원 경로 노드: {node.type.name}.", node)
        if node.type == NodeType.THROW:
            continue
        states = [path]
        for ir in node.irs:
            following = []
            for p in states:
                if isinstance(ir, Index):
                    base = symbol(ir.variable_left) if isinstance(ir.variable_left, StateVariable) else p.refs.get(ir.variable_left)
                    if base is None:
                        raise Unsupported("storage 이외의 인덱스는 지원하지 않습니다.")
                    p.refs[ir.lvalue] = ("index", base, p.read(ir.variable_right))
                elif isinstance(ir, Assignment):
                    p.write(ir.lvalue, p.read(ir.rvalue), node)
                elif isinstance(ir, Binary):
                    op = ir.type.name
                    if op not in {"ADDITION", "SUBTRACTION", "MULTIPLICATION", "EQUAL", "NOT_EQUAL",
                                  "LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL", "ANDAND", "OROR"}:
                        raise Unsupported(f"미지원 경로 연산: {op}.", node)
                    a, b = p.read(ir.variable_left), p.read(ir.variable_right)
                    expr = simplify(op, a, b)
                    if op in {"ADDITION", "SUBTRACTION", "MULTIPLICATION"}:
                        if not node.scope.is_checked or str(ir.lvalue.type) != "uint256":
                            raise Unsupported("unchecked 또는 uint256 외 산술은 지원하지 않습니다.")
                        p.checked.append((expr, node))
                    p.write(ir.lvalue, expr, node)
                elif isinstance(ir, Unary):
                    if ir.type.name != "BANG":
                        raise Unsupported("논리 부정 이외의 단항 연산은 지원하지 않습니다.")
                    p.write(ir.lvalue, negate(p.read(ir.rvalue)), node)
                elif isinstance(ir, Condition):
                    p.values[("branch", node)] = p.read(ir.value)
                elif isinstance(ir, TypeConversion):
                    expr = p.read(ir.variable)
                    if str(ir.type) == "address" and expr == ZERO:
                        expr = ZERO_ADDRESS
                    elif str(ir.type) in {"address", "address payable"} and (expr == THIS or str(ir.variable.type) in {"address", "address payable"}):
                        pass
                    else:
                        raise Unsupported("값 손실 가능 타입 변환은 지원하지 않습니다.")
                    p.values[ir.lvalue] = expr
                elif isinstance(ir, SolidityCall):
                    name = ir.function.name
                    if name in {"require(bool)", "require(bool,string)", "assert(bool)"}:
                        if not p.guard(p.read(ir.arguments[0]), node):
                            continue
                    elif name.startswith("revert("):
                        continue
                    elif name == "balance(address)" and p.read(ir.arguments[0]) == THIS:
                        p.values[ir.lvalue] = ETHER
                    else:
                        raise Unsupported(f"미지원 Solidity 내장 연산: {name}.")
                elif isinstance(ir, InternalCall):
                    callee = ir.function
                    if callee is None or callee.is_constructor:
                        raise Unsupported("동적 내부 호출/상속 생성자 인자는 지원하지 않습니다.")
                    if any(str(v.type).startswith(("mapping", "struct")) for v in callee.parameters):
                        raise Unsupported("내부 함수의 storage 인자는 지원하지 않습니다.")
                    args = [p.read(v) for v in ir.arguments]
                    if len(args) != len(callee.parameters):
                        raise Unsupported("내부 호출 인자를 연결하지 못했습니다.")
                    nested = p.clone()
                    nested.values.update(zip(callee.parameters, args))
                    for result in trace_paths(callee, nested, stack):
                        if isinstance(callee, Modifier) and len(result.writes) != len(p.writes):
                            raise Unsupported("상태를 변경하는 modifier는 아직 지원하지 않습니다.")
                        if ir.lvalue is not None:
                            if len(result.result) != 1:
                                raise Unsupported("내부 함수의 복수/암묵적 반환값은 지원하지 않습니다.")
                            result.values[ir.lvalue] = result.result[0]
                        result.result, result.stopped = (), False
                        following.append(result)
                    continue
                elif isinstance(ir, EventCall):
                    pass
                elif isinstance(ir, LowLevelCall):
                    if ir.call_gas is not None or len(p.calls) >= 1:
                        raise Unsupported("지정 gas 또는 경로당 복수 외부 호출은 지원하지 않습니다.")
                    call = {"kind": ir.function_name.value, "destination": p.read(ir.destination),
                            "arguments": [p.read(a) for a in ir.arguments],
                            "value": p.read(ir.call_value) if ir.call_value is not None else None,
                            "node": node, "writes_before": len(p.writes)}
                    p.calls.append(call)
                    p.steps.append(("call", call))
                    p.values[ir.lvalue] = ("call_result", len(p.calls) - 1)
                elif isinstance(ir, Unpack):
                    result = p.read(ir.tuple)
                    if result[0] != "call_result" or ir.index != 0:
                        raise Unsupported("호출 성공 여부 외 반환 데이터는 지원하지 않습니다.")
                    p.values[ir.lvalue] = ("call_success", result[1])
                elif isinstance(ir, Return):
                    p.result = tuple(p.read(v) for v in ir.values)
                    p.stopped = True
                else:
                    raise Unsupported(f"미지원 경로 IR: {type(ir).__name__}.", node)
                following.append(p)
            states = following
        for p in states:
            if node.type == NodeType.IF:
                condition = p.values[("branch", node)]
                for son, guard in ((node.son_true, condition), (node.son_false, negate(condition))):
                    branch = p.clone()
                    if branch.guard(guard, node):
                        queue.append((son, branch, visited))
            elif len(node.sons) <= 1:
                queue.append((node.sons[0] if node.sons else None, p, visited))
            else:
                raise Unsupported("분기 노드 이외의 복수 후속 경로입니다.")
    return completed


def contract_paths(contract):
    if contract.is_abstract or not contract.is_fully_implemented:
        raise Unsupported("배포할 수 없는 추상/미완성 컨트랙트입니다.")
    constructors = [f for f in contract.functions if f.is_constructor]
    if len(constructors) > 1:
        raise Unsupported("복수 상속 생성자의 실행 순서/인자는 아직 지원하지 않습니다.")
    initial, runtime = [], []
    for function in contract.functions:
        if function.is_constructor or function.is_constructor_variables:
            paths = trace_paths(function)
            if len(paths) != 1 or function.payable or paths[0].calls:
                raise Unsupported("분기/예치/외부 호출 생성자는 지원하지 않습니다.")
            initial.append((function, paths[0]))
        elif function.visibility in {"public", "external"}:
            if not function.is_implemented:
                raise Unsupported("구현 없는 외부 함수입니다.")
            runtime.extend((function, p) for p in trace_paths(function))
    initial.sort(key=lambda item: item[0].is_constructor)
    for _, path in initial + runtime:
        limitation = validate_checked(path.checked, path.guards, path.writes)
        if limitation:
            raise Unsupported(limitation)
    return initial, runtime


def location_evidence(node):
    return {"function": node.function.full_name, "line": min(node.source_mapping.lines)}
