"""Closed token ledger schemas, independent of an explicit aggregate supply.

No mint inference from names. Initial credit, conservation transfers, permissions
and optional paired burns establish the model. Unsupported writes fail closed.
"""
from .linear import SENDER, Unsupported, symbol
from functools import partial
from ..reporting import contextual_result, explain, location
from .supply import is_balance, index, equal, is_parameter, zero_check
from .fixed_supply import allowance_type
from .paths import contract_paths, ZERO, TRUE, negate, flatten
from .expanded_tokens import (root, guards, initialized, transfer_shape,
                              parameter_condition, owner_guard, result, is_uint, capped)


def bounded_issuance(initial, runtime, values, owners, balance):
    """A zero-initialized, capped quantity ledger; no claim of tradability."""
    fixed = {v: x[2] for v, x in values.items() if v.is_constant and is_uint(x)}
    totals, nodes = set(), []
    for f, p in runtime:
        if not p.writes:
            continue
        if len(p.writes) != 2 or not owner_guard(p, owners):
            raise Unsupported("전송 없는 수량 장부는 고정 상한 발행만 지원합니다.")
        aggregates = [w for w in p.writes if w[0][0] == "variable" and str(w[0][1].type) == "uint256"]
        credits = [w for w in p.writes if w[0][0] == "index" and root(w[0]) == balance]
        if len(aggregates) != 1 or len(credits) != 1:
            raise Unsupported("수량 장부와 총량 증가 연결 미확인")
        loc, value, node = aggregates[0]
        credit, increase, _ = credits[0]
        if (value[0] != "ADDITION" or value[1] != loc
                or not is_parameter(value[2], f, "uint256")
                or not is_parameter(credit[2], f, "address")
                or increase != ("ADDITION", credit, value[2])
                or values.get(loc[1], ZERO) != ZERO or not capped(p, value, fixed)):
            raise Unsupported("전송 없는 발행의 초기 총량/고정 상한을 확인하지 못했습니다.")
        totals.add(loc[1])
        nodes.append(node)
    if len(totals) != 1 or any(root(loc) == balance for _, p in initial for loc, _, _ in p.writes):
        raise Unsupported("전송 없는 수량 장부의 초기 상태 미확인")
    return contextual_result("BENIGN", "초기 수량 장부와 총량은 0이며 모든 상태 변경은 동일량 발행입니다. 실제 증가 후 총량에 변경 불가능한 상한이 적용되고 외부 호출이나 다른 잔액 변경은 없습니다. 전송 가능성이나 시장 가치는 추정하지 않았습니다.", nodes, contexts=initial + runtime)


def analyze_contract(contract):
    initial, runtime = contract_paths(contract)
    finish = partial(contextual_result, contexts=initial + runtime)
    if any(f.payable or p.calls for f, p in runtime):
        raise Unsupported("장부 연산 규칙은 외부 호출/예치를 다루지 않습니다.")
    values, owners, _ = initialized(initial)
    balances = [v for v in contract.state_variables if is_balance(v)]
    if len(balances) != 1:
        raise Unsupported("단일 주소별 장부가 필요합니다.")
    balance = balances[0]
    allowances = {v for v in contract.state_variables if allowance_type(v)}
    credits = [(f, loc, value, n) for f, p in initial for loc, value, n in p.writes
               if root(loc) == balance]
    if not credits:
        return bounded_issuance(initial, runtime, values, owners, balance)
    if len(credits) != 1 or credits[0][1] != index(balance, SENDER):
        raise Unsupported("배포자 초기 장부 할당을 확인하지 못했습니다.")
    constructor, _, quantity, init_node = credits[0]
    if not (is_uint(quantity) or is_parameter(quantity, constructor, "uint256")):
        raise Unsupported("초기 장부 수량의 유래를 확인하지 못했습니다.")
    totals = {v for v, value in values.items()
              if str(v.type) == "uint256" and value == quantity and not v.is_constant}
    if len(totals) > 1:
        raise Unsupported("초기 총량 역할이 모호합니다.")
    supply = next(iter(totals), None)
    # The initializer may not seed permissions or a second hidden asset ledger.
    for _, p in initial:
        for loc, value, _ in p.writes:
            if loc[0] == "index" and root(loc) != balance:
                if not (str(root(loc).type) == "mapping(address => bool)"
                        and loc[2] == SENDER and value == TRUE):
                    raise Unsupported("추가 초기 장부/승인 쓰기는 지원하지 않습니다.")

    controls, switches, lists, destinations = set(), set(), set(), set()
    for f, p in runtime:
        if len(p.writes) != 1 or not owner_guard(p, owners):
            continue
        loc, value, _ = p.writes[0]
        if not all(any(equal(g, SENDER, symbol(o)) for o in owners)
                   or any(zero_check(g, symbol(v)) for v in f.parameters if str(v.type) == "address")
                   for g in guards(p)):
            continue
        if loc[0] == "variable" and str(loc[1].type) == "bool" and is_parameter(value, f, "bool"):
            switches.add(loc)
        elif (loc[0] == "index" and str(root(loc).type) == "mapping(address => bool)"
              and is_parameter(loc[2], f, "address") and is_parameter(value, f, "bool")):
            lists.add(root(loc))
        elif (loc[0] == "variable" and loc[1] not in owners
              and str(loc[1].type) == "address" and is_parameter(value, f, "address")):
            destinations.add(loc)
        else:
            continue
        controls.add(id(p))

    transfers, burns, safe_nodes, unknown = [], [], [init_node], []
    approval_stores = set()
    for f, p in runtime:
        if id(p) in controls or not p.writes:
            continue
        if len(p.writes) == 1:
            loc, value, n = p.writes[0]
            if (loc[0] == "index" and loc[1][0] == "index" and root(loc) in allowances
                    and loc[1][2] == SENDER and is_parameter(loc[2], f, "address")
                    and is_parameter(value, f, "uint256")):
                # Safety of setting one's own permission is independent of its
                # availability. A funding witness, however, needs usable approval.
                if all(parameter_condition(g, f) or any(equal(g, SENDER, symbol(o)) for o in owners)
                       for g in guards(p)):
                    approval_stores.add(root(loc))
                safe_nodes.append(n)
                continue
        shape = transfer_shape(p, balance)
        if shape:
            origin, recipient, amount, node = shape
            if not (is_parameter(amount, f, "uint256")
                    and (origin == SENDER or is_parameter(origin, f, "address"))
                    and is_parameter(recipient, f, "address")):
                unknown.append("전송 입력 연결 미지원")
                continue
            extras = [w for w in p.writes if root(w[0]) != balance]
            transfers.append((f, p, origin, recipient, amount, node, extras))
            continue
        # Burn is a paired decrement, irrespective of assignment order.
        debits = [w for w in p.writes if root(w[0]) == balance]
        totals_written = [w for w in p.writes if supply is not None and w[0] == symbol(supply)]
        if len(debits) == len(totals_written) == 1:
            loc, value, node = debits[0]
            if loc[0] == "index" and value[0] == "SUBTRACTION" and value[1] == loc:
                amount = value[2]
                if (is_parameter(amount, f, "uint256") and
                        totals_written[0][1] == ("SUBTRACTION", symbol(supply), amount)):
                    extras = [w for w in p.writes if w not in debits + totals_written]
                    burns.append((f, p, loc[2], None, amount, node, extras))
                    continue
        unknown.append("전송/승인/동일량 소각 이외의 상태 변경")
    if unknown:
        raise Unsupported("; ".join(sorted(set(unknown))))
    if not transfers and not burns:
        raise Unsupported("장부 사용 연산을 확인하지 못했습니다.")

    # Match a complete two-path destination gate, including its bypass path.
    destination_paths = set()
    for f, p, origin, recipient, amount, node, extras in transfers:
        if origin != SENDER or extras:
            continue
        base = [g for g in guards(p) if g != ("LESS_EQUAL", amount, index(balance, origin))
                and not parameter_condition(g, f)]
        if len(base) != 1 or base[0][0] != "NOT" or base[0][1][0] != "ANDAND":
            continue
        branch = base[0][1]
        terms = flatten(branch)
        if len(terms) != 2:
            continue
        destination_gate = any(equal(g, recipient, d) for g in terms for d in destinations)
        owner_exception = any(g in {negate(("EQUAL", SENDER, symbol(o))),
                                    negate(("EQUAL", symbol(o), SENDER))}
                              for g in terms for o in owners)
        if not destination_gate or not owner_exception:
            continue
        for other_f, other, other_origin, other_recipient, other_amount, _, other_extras in transfers:
            if (other_f != f or other_origin != origin or other_recipient != recipient
                    or other_amount != amount or other_extras):
                continue
            other_base = [g for g in guards(other)
                          if g != ("LESS_EQUAL", amount, index(balance, origin))
                          and not parameter_condition(g, f)]
            tail = [g for g in other_base if g not in terms]
            if (all(g in other_base for g in terms) and len(tail) == 1
                    and (tail[0] in switches or (tail[0][0] == "NOT" and tail[0][1] in switches))):
                destination_paths.update((id(p), id(other)))

    risks, risk_nodes, authorized_transfers = [], [], []
    pending_thefts = []
    for f, p, origin, recipient, amount, node, extras in transfers + burns:
        permissions = {("index", index(a, origin), SENDER) for a in allowances}
        consumed = (len(extras) == 1 and extras[0][0] in permissions
                    and extras[0][1] == ("SUBTRACTION", extras[0][0], amount))
        own = origin == SENDER or any(equal(g, origin, SENDER) for g in guards(p))
        if extras and not consumed:
            raise Unsupported("승인 차감의 대상/금액 또는 추가 상태 변경 미확인")
        restriction = [g for g in guards(p) if not (
            parameter_condition(g, f) or equal(g, origin, SENDER)
            or g == ("LESS_EQUAL", amount, index(balance, origin))
            or any(g == ("LESS_EQUAL", amount, a) for a in permissions)
            or any(equal(g, SENDER, symbol(o)) for o in owners))]
        # Non-owner branch of an allowance bypass is an ordinary authorized path.
        restriction = [g for g in restriction if not any(
            g == negate(("EQUAL", SENDER, symbol(o))) or g == negate(("EQUAL", symbol(o), SENDER))
            for o in owners)] if consumed else restriction
        if not own and not consumed:
            if restriction or not is_parameter(origin, f, "address"):
                raise Unsupported("무단 장부 차감 경로의 조건을 해석하지 못했습니다.")
            if any(g == ("LESS_EQUAL", amount, permission) and root(permission) not in approval_stores
                   for g in guards(p) for permission in permissions):
                raise Unsupported("승인 조건이 있지만 양수 승인을 설정할 경로를 확인하지 못했습니다.")
            pending_thefts.append((node, bool(owner_guard(p, owners)), recipient is None))
            continue
        if recipient is None and restriction:
            raise Unsupported("소각 경로의 추가 조건 미지원")
        if restriction and owner_guard(p, owners):
            raise Unsupported("관리자 전용 경로의 제약을 일반 보유자 차단으로 해석할 수 없습니다.")
        if id(p) in destination_paths:
            risks.append("관리자가 지정하는 목적지로의 전송에 일반 보유자만 상태 제약을 받으며 관리자는 우회합니다. 목적지와 제한 상태 모두 관리자 변경 경로에 연결됩니다.")
            risk_nodes.append(node)
            restriction = []
        for g in restriction:
            if g in switches or (g[0] == "NOT" and g[1] in switches):
                continue
            if g[0] == "OROR" and any(
                any(equal(b, SENDER, symbol(o)) for o in owners)
                and (a in switches or (a[0] == "NOT" and a[1] in switches))
                for a, b in [(g[1], g[2]), (g[2], g[1])]):
                if g[1] in restriction or g[2] in restriction:
                    continue  # A separate symmetric guard still binds the owner.
                risks.append("관리자가 정지 상태를 변경하고 자신은 전송 제한을 우회합니다. 일반 보유자에게만 적용되는 비대칭 제약입니다.")
                risk_nodes.append(node)
                continue
            if (g[0] == "index" and root(g) in lists and g[2] == SENDER
                    and any(loc == g and value == TRUE for _, ip in initial for loc, value, _ in ip.writes)):
                risks.append("배포자는 초기 허용되고 관리자가 발신자 허용 목록을 변경합니다. 일반 수령자의 재전송을 선택적으로 차단할 수 있습니다.")
                risk_nodes.append(node)
                continue
            raise Unsupported("전송 제약의 대칭성/실행 가능성 미확인")
        if recipient is not None and (own or (consumed and root(extras[0][0]) in approval_stores)):
            authorized_transfers.append(node)
        safe_nodes.append(node)
    # Owner-only debit of an unreachable third-party balance is not theft evidence.
    if quantity == ZERO and (risks or pending_thefts):
        raise Unsupported("초기 수량이 0이고 발행이 없어 피해 자산에 도달하지 못합니다.")
    for node, privileged, burn in pending_thefts:
        if privileged and not authorized_transfers:
            raise Unsupported("관리자 외 보유자의 양수 잔액 도달 경로를 확인하지 못했습니다.")
        risks.append("초기 장부 또는 정상 전송으로 보유한 잔액을 당사자 확인이나 승인 한도 차감 없이 "
                     + ("소각할 수 있습니다." if burn else "다른 주소로 이전할 수 있습니다."))
        risk_nodes.append(node)
    if risks:
        return explain({"verdict": "MALICIOUS", "reasons": risks,
                        "_reason_evidence": [[location(n)] for n in risk_nodes],
                        "evidence": [location(n) for n in risk_nodes]}, initial + runtime)
    operations = "/".join(name for name, present in (("전송", transfers), ("소각", burns)) if present)
    return finish("BENIGN", "초기 장부 할당과 모든 상태 변경을 확인했습니다. " + operations + "은 자기 잔액 또는 동일 금액을 차감하는 승인 한도를 사용합니다. "
                  + ("소각은 총량과 잔액을 동일하게 감소시킵니다. " if burns else "")
                  + "추가 발행/외부 호출 경로는 없습니다. "
                  + ("분석한 정지 조건은 모든 호출자에게 동일하게 적용됩니다." if switches else ""), safe_nodes)
