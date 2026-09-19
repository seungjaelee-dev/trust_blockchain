"""Small token schemas over bounded paths: invariants, authority and cap bypasses.

Safety requires every reachable path to match an accounted-for operation. Risk
rules accept only understood guards; unsupported conditions never mean no guard.
"""
from slither.core.variables.state_variable import StateVariable
from functools import partial
from ..reporting import contextual_result, explain
from .linear import SENDER, ZERO_ADDRESS, Unsupported, symbol
from .supply import is_balance, index, is_parameter, equal, zero_check
from .fixed_supply import allowance_type
from .paths import (contract_paths, location_evidence, ZERO, TRUE, FALSE, negate,
                    UINT_MAX, flatten)


def root(loc):
    while loc[0] == "index":
        loc = loc[1]
    return loc[1] if loc[0] == "variable" else None


def guards(path):
    return [g for g, _ in path.guards]


def is_uint(expr):
    return expr[0] == "constant" and expr[1] == "uint256" and 0 <= expr[2] <= UINT_MAX


def numeric(expr, constants):
    if is_uint(expr):
        return expr[2]
    if expr[0] == "variable":
        value = constants.get(expr[1])
        return value[2] if value and is_uint(value) else None
    return None


def includes(expr, needle):
    return expr == needle or any(includes(x, needle) for x in expr[1:] if isinstance(x, tuple))


def initialized(initial):
    values, owners, evidence = {}, set(), []
    for function, path in initial:
        if path.guards:
            raise Unsupported("초기화 검사식의 전역 불변조건은 아직 지원하지 않습니다.")
        for loc, value, node in path.writes:
            if loc[0] == "variable":
                values[loc[1]] = value
                if value == SENDER and str(loc[1].type) == "address":
                    owners.add(loc[1])
            evidence.append(location_evidence(node))
    return values, owners, evidence


def owner_guard(path, owners):
    return next((v for v in owners if any(equal(g, SENDER, symbol(v)) for g in guards(path))), None)


def parameter_condition(g, function):
    if is_parameter(g, function, "bool") or (g[0] == "NOT" and is_parameter(g[1], function, "bool")):
        return True
    return any(zero_check(g, symbol(v)) for v in function.parameters if str(v.type) == "address")


def transfer_shape(path, balance):
    writes = [w for w in path.writes if root(w[0]) == balance]
    if len(writes) != 2:
        return None
    (debit, sub, node), (credit, add, _) = writes
    if (debit[0] != "index" or credit[0] != "index" or sub[0] != "SUBTRACTION"
            or sub[1] != debit or add != ("ADDITION", credit, sub[2])):
        return None
    return debit[2], credit[2], sub[2], node


def cap_bounds(runtime, values):
    """Numeric state bounds proved from initialization AND every assignment path."""
    bounds = {v: x[2] for v, x in values.items() if is_uint(x) and v.is_constant}
    setters = {}
    for function, path in runtime:
        for loc, value, node in path.writes:
            if loc[0] == "variable":
                setters.setdefault(loc[1], []).append((function, path, value, node))
    # Read-only initialized numeric state is also fixed; no names needed.
    for variable, value in values.items():
        if is_uint(value) and variable not in setters:
            bounds[variable] = value[2]
    for variable, writes in setters.items():
        if variable not in values or not is_uint(values[variable]):
            continue
        limits = [values[variable][2]]
        for _, path, value, _ in writes:
            fixed_values = {v: x for v, x in values.items() if v not in setters}
            options = [numeric(g[2], fixed_values) for g in guards(path)
                       if g[0] == "LESS_EQUAL" and g[1] == value]
            options = [n for n in options if n is not None]
            if is_uint(value):
                options.append(value[2])
            if not options:
                break
            limits.append(min(options))
        else:
            bounds[variable] = max(limits)
    return bounds, setters


def capped(path, new_supply, bounds):
    for g, node in path.guards:
        if g[0] == "LESS_EQUAL" and g[1] == new_supply:
            cap = g[2]
            limit = cap[2] if is_uint(cap) else bounds.get(cap[1]) if cap[0] == "variable" else None
            if limit is not None and 0 < limit < UINT_MAX:
                return node
    return None


def result(verdict, reason, nodes):
    evidence = []
    for node in nodes:
        item = location_evidence(node)
        if item not in evidence:
            evidence.append(item)
    return {"verdict": verdict, "reasons": [reason], "evidence": evidence}


def analyze_contract(contract):
    initial, runtime = contract_paths(contract)
    finish = partial(contextual_result, contexts=initial + runtime)
    if any(f.payable or p.calls for f, p in runtime):
        raise Unsupported("토큰 확장 규칙은 예치/외부 호출을 처리하지 않습니다.")
    values, owners, _ = initialized(initial)
    # Financial role comes from a conservation transfer, not a variable name.
    candidates = {v for v in contract.state_variables if is_balance(v)}
    candidates = {v for v in candidates if any(transfer_shape(p, v) and transfer_shape(p, v)[0] == SENDER for _, p in runtime)}
    if len(candidates) != 1:
        raise Unsupported("보존적 직접 전송으로 단일 잔액 장부를 식별하지 못했습니다.")
    balance = candidates.pop()
    allowances = {v for v in contract.state_variables if allowance_type(v)}
    bounds, setters = cap_bounds(runtime, values)
    risks, risk_nodes, safe_nodes, unexplained = [], [], [], []
    risk_kinds = []  # Report identity only; never used to decide a verdict.
    supplies, minted, init_supply = set(), [], None
    capped_issues, zero_issues = 0, 0
    controlled_bool, lists, unlimited_caps = set(), set(), set()

    # Assignments are recognized separately; their effect on caps/transfer guards
    # is still checked at the point those values are used.
    control_paths = set()
    for function, path in runtime:
        if len(path.writes) != 1:
            continue
        loc, value, node = path.writes[0]
        owner = owner_guard(path, owners)
        only_control_guards = all(any(equal(g, SENDER, symbol(o)) for o in owners)
                                 or parameter_condition(g, function)
                                 or (g[0] == "LESS_EQUAL" and g[1] == value and numeric(g[2], values) is not None)
                                 for g in guards(path))
        if not only_control_guards:
            continue
        if loc[0] == "variable" and loc[1] in owners and is_parameter(value, function, "address"):
            if owner:
                control_paths.add(id(path))
            else:
                unexplained.append("외부 호출자가 관리자 값을 변경할 수 있으나 후속 자산 영향 검토가 필요합니다.")
        elif loc[0] == "variable" and str(loc[1].type) == "bool" and owner and is_parameter(value, function, "bool"):
            controlled_bool.add(loc)
            control_paths.add(id(path))
        elif (loc[0] == "index" and str(root(loc).type) == "mapping(address => bool)"
              and owner and is_parameter(loc[2], function, "address") and is_parameter(value, function, "bool")):
            lists.add(root(loc))
            control_paths.add(id(path))
        elif loc[0] == "variable" and loc[1] in values and is_uint(values[loc[1]]) and owner and is_parameter(value, function, "uint256"):
            control_paths.add(id(path))
            if loc[1] not in bounds:
                unlimited_caps.add(loc[1])

    for function, path in runtime:
        if id(path) in control_paths:
            continue
        if not path.writes:
            continue
        transfer = transfer_shape(path, balance)
        if transfer:
            origin, recipient, amount, node = transfer
            if not (is_parameter(amount, function, "uint256") and
                    (recipient == SENDER or is_parameter(recipient, function, "address"))):
                unexplained.append("전송 입력값 연결 미지원")
                continue
            extras = [w for w in path.writes if root(w[0]) != balance]
            # Solidity 0.8 checked subtraction also enforces the allowance ceiling.
            permission = next((("index", index(a, origin), SENDER) for a in allowances), None)
            consumed = (permission is not None and len(extras) == 1 and extras[0][0] == permission
                        and extras[0][1] == ("SUBTRACTION", permission, amount))
            own = origin == SENDER or any(equal(g, origin, SENDER) for g in guards(path))
            ordinary = []
            restriction = []
            for g in guards(path):
                if (parameter_condition(g, function) or g == ("LESS_EQUAL", amount, index(balance, origin))
                        or (permission is not None and g == ("LESS_EQUAL", amount, permission))
                        or equal(g, origin, SENDER) or any(equal(g, SENDER, symbol(o)) for o in owners)):
                    ordinary.append(g)
                else:
                    restriction.append(g)
            if not own and not consumed:
                if not restriction and not extras and is_parameter(origin, function, "address"):
                    risk_kinds.append("unauthorized_transfer")
                    risks.append("외부 호출자가 타인 잔액을 차감해 같은 양을 다른 주소로 옮길 수 있습니다. "
                                 + ("승인 한도 검사는 있으나 사용분 차감이 없어 반복 사용으로 승인 총량을 넘길 수 있습니다."
                                    if permission is not None and ("LESS_EQUAL", amount, permission) in guards(path)
                                    else "당사자/승인 한도 차감에 의한 보호가 없습니다."))
                    risk_nodes.append(node)
                else:
                    unexplained.append("대리 전송의 권한/성공 경로 미확인")
                continue
            if extras and not consumed:
                unexplained.append("전송 외 추가 쓰기 미지원")
                continue
            valid = True
            for g in restriction:
                if g in controlled_bool or (g[0] == "NOT" and g[1] in controlled_bool):
                    continue  # Equal availability constraint on everyone.
                if g[0] == "OROR":
                    a, b = g[1:]
                    if any(equal(b, SENDER, symbol(o)) for o in owners) and (a in controlled_bool or (a[0] == "NOT" and a[1] in controlled_bool)):
                        risk_kinds.append("asymmetric_pause")
                        risks.append("전송 제한 상태는 소유자가 변경하며, 소유자는 동일 제한을 우회해 전송할 수 있습니다. 일반 보유자만 차단되는 비대칭 제약입니다.")
                        risk_nodes.append(node)
                        continue
                if g[0] == "index" and root(g) in lists and g[2] == SENDER:
                    enabled = any(loc == g and value == TRUE for _, init in initial for loc, value, _ in init.writes)
                    if enabled and owners:
                        risk_kinds.append("sender_allowlist")
                        risks.append("소유자는 생성자에서 초기 허용되고 목록 변경을 통제합니다. 발신자 제한 때문에 일반 수령자는 허용 전까지 재전송할 수 없습니다.")
                        risk_nodes.append(node)
                        continue
                valid = False
            if not valid:
                unexplained.append("전송 제한의 대칭성/역할 미확인")
            safe_nodes.append(node)
            continue
        # Self approval is not a transfer and cannot write somebody else's permission.
        if len(path.writes) == 1:
            loc, value, node = path.writes[0]
            if (root(loc) in allowances and loc[0] == "index" and loc[1][0] == "index"
                    and loc[1][2] == SENDER and is_parameter(loc[2], function, "address")
                    and is_parameter(value, function, "uint256")):
                safe_nodes.append(node)
                continue
        # Mint: the very same increment must update aggregate and usable balances.
        if len(path.writes) == 2:
            (loc, value, node), (credit, increase, _) = path.writes
            if (loc[0] == "variable" and str(loc[1].type) == "uint256" and value[0] == "ADDITION"
                    and value[1] == loc and credit[0] == "index" and root(credit) == balance
                    and increase == ("ADDITION", credit, value[2]) and is_parameter(value[2], function, "uint256")):
                supplies.add(loc[1])
                minted.append((function, path, loc[1]))
                if values.get(loc[1]) == ("constant", "uint256", UINT_MAX):
                    unexplained.append("초기 공급량이 uint256 최대여서 양수 발행의 실행 가능성을 확인하지 못했습니다.")
                    continue
                cap_node = capped(path, value, bounds)
                if any(equal(g, value[2], ZERO) for g in guards(path)):
                    zero_issues += 1
                    safe_nodes.append(node)
                    continue
                if cap_node:
                    capped_issues += 1
                    safe_nodes.append(cap_node)
                    continue
                owner = owner_guard(path, owners)
                understood = owner is not None
                issue = "해당 성공 경로에 총공급량 상한 검사가 없습니다."
                for g in guards(path):
                    if owner is not None and equal(g, SENDER, symbol(owner)):
                        continue
                    if parameter_condition(g, function):
                        continue
                    if g[0] == "LESS_EQUAL" and g[1] == value[2]:
                        # A per-call quota allows repeated issues; it is not a total cap.
                        quota = numeric(g[2], {v: x for v, x in values.items() if v not in setters})
                        if quota is not None and quota > 0:
                            issue = "한 번의 발행량만 제한하고 반복 발행의 총공급량은 제한하지 않습니다."
                            continue
                    # Wrong parameter checked against a cap, or mutable cap with an unrestricted setter.
                    if (g[0] == "LESS_EQUAL" and g[1][0] == "ADDITION" and g[1][1] == loc
                            and is_parameter(g[1][2], function, "uint256") and g[2][0] == "variable"):
                        capvar = g[2][1]
                        if (g[1][2] != value[2] and capvar in bounds and bounds[capvar] > 0) or capvar in unlimited_caps:
                            issue = ("상한 자체를 소유자가 고정된 최종 경계 없이 변경할 수 있습니다."
                                     if capvar in unlimited_caps else "검사한 증가량과 실제 공급량/잔액 증가량이 서로 다른 입력입니다.")
                            continue
                    understood = False
                if understood:
                    if any(is_parameter(g, function, "bool") or (g[0] == "NOT" and is_parameter(g[1], function, "bool")) for g in guards(path)):
                        issue += " 호출자가 선택하는 분기의 검사 우회 경로입니다."
                    risk_kinds.append("unbounded_mint")
                    risks.append("소유자 발행 경로에서 실제 공급량 증가를 제한하는 고정 상한이 강제되지 않습니다. " + issue + " "
                                 "동일 증가량이 전송 가능한 잔액에도 반영되어 보유자 지분을 희석할 수 있습니다.")
                    risk_nodes.append(node)
                else:
                    unexplained.append("발행 조건의 상한/경로 실행 가능성을 확정하지 못했습니다.")
                continue
        unexplained.append("설명되지 않은 상태 변경 경로")

    # Constructor must account for every initial token/aggregate balance assignment.
    constructor_writes = [(loc, value, node) for f, p in initial if f.is_constructor for loc, value, node in p.writes]
    initial_credits = [(loc, value, node) for loc, value, node in constructor_writes if root(loc) == balance]
    if initial_credits:
        if len(initial_credits) != 1 or initial_credits[0][0] != index(balance, SENDER):
            raise Unsupported("초기 잔액 분배 범위를 검증하지 못했습니다.")
        quantity = initial_credits[0][1]
        possible = [loc[1] for loc, value, _ in constructor_writes
                    if loc[0] == "variable" and str(loc[1].type) == "uint256" and value == quantity]
        if len(possible) != 1:
            raise Unsupported("초기 공급량/잔액 동일성 미확인")
        init_supply = possible[0]
        supplies.add(init_supply)
    if len(supplies) != 1:
        raise Unsupported("단일 총공급량 역할을 확인하지 못했습니다.")
    supply = next(iter(supplies))
    if any(id(p) in control_paths and any(root(loc) == supply for loc, _, _ in p.writes) for _, p in runtime):
        unexplained.append("총공급량을 발행 외 관리 함수가 덮어쓰는 경로")
    if any(root(loc) == balance for f, p in initial if f.is_constructor_variables for loc, _, _ in p.writes):
        raise Unsupported("선언부 잔액 초기화 미지원")
    if minted and init_supply is not None:
        # Preserve risk evidence but do not claim safety for unchecked initial mint.
        unexplained.append("초기 공급량과 발행 상한의 전역 관계 미확인")
    if risks:
        if not minted and values.get(supply) == ZERO:
            raise Unsupported("고정 공급량이 0이라 위험 경로에 영향을 받는 보유자 자산을 확인하지 못했습니다.")
        return explain({"verdict": "MALICIOUS", "reasons": risks,
                "_reason_kinds": risk_kinds,
                "_reason_evidence": [[location_evidence(n)] for n in risk_nodes],
                "evidence": result("MALICIOUS", "", risk_nodes)["evidence"]}, initial + runtime)
    if unexplained:
        raise Unsupported("; ".join(dict.fromkeys(unexplained)))
    supply_reason = "공급량은 초기화 후 변경되지 않습니다. " if not minted else ""
    if capped_issues:
        supply_reason += "발행 경로에서 실제 증가 후 공급량의 고정된 최종 상한을 확인했습니다. "
    if zero_issues:
        supply_reason += "발행량을 반드시 0으로 제한하는 경로도 확인했습니다. "
    return finish("BENIGN", "지원하는 모든 성공 경로와 내부 호출을 확인했습니다. " + supply_reason +
                  "전송은 자기 잔액 또는 차감되는 승인 한도를 사용하며 외부 호출은 없습니다. " +
                  ("정지 제약은 소유자에게도 동일하게 적용됩니다. " if controlled_bool else "") +
                  ("소유자의 관리 권한은 중앙화 위험으로 남습니다." if owners else ""), safe_nodes)
