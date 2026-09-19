"""Evidence-bound explanations. Formatting never decides a verdict."""
from dataclasses import dataclass
import json


def unique(items):
    result, seen = [], set()
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def location(item):
    if isinstance(item, dict):
        return dict(item)
    evidence = {"line": min(item.source_mapping.lines)}
    function = getattr(item, "function", None)
    if function is not None and not function.is_constructor_variables:
        evidence["function"] = function.full_name
    return evidence


@dataclass
class Claim:
    text: str
    evidence: list
    scope: str = "컨트랙트 전체 분석"


def claim(text, nodes=(), scope="컨트랙트 전체 분석"):
    return Claim(text.strip(), unique([location(n) for n in nodes]), scope)


def render(verdict, claims, primary=()):
    reasons, evidence = [], [location(n) for n in primary]
    for item in claims:
        groups = {}
        for ref in item.evidence:
            groups.setdefault(ref.get("function", "상태 선언"), []).append(ref["line"])
        labels = [f"{function}, {', '.join(str(n) for n in sorted(set(lines)))}행"
                  for function, lines in groups.items()]
        reasons.append(f"[{' · '.join(labels) if labels else item.scope}] {item.text}")
        evidence.extend(item.evidence)
    return {"verdict": verdict, "reasons": unique(reasons), "evidence": unique(evidence)}


OPS = {"EQUAL": "==", "NOT_EQUAL": "!=", "LESS_EQUAL": "<=", "GREATER_EQUAL": ">=",
       "LESS": "<", "GREATER": ">", "ADDITION": "+", "SUBTRACTION": "-",
       "MULTIPLICATION": "*", "ANDAND": "&&", "OROR": "||"}


def expression(expr):
    """Display declaration-linked symbolic values; never interpret names as roles."""
    kind = expr[0]
    if kind == "variable":
        return expr[1].name
    if kind == "builtin":
        return {"ether_balance": "address(this).balance"}.get(expr[1], expr[1])
    if kind == "constant":
        if expr[1] == "bool":
            return "true" if expr[2] else "false"
        if expr[1] == "address" and expr[2] == 0:
            return "address(0)"
        return json.dumps(expr[2], ensure_ascii=False) if isinstance(expr[2], str) else str(expr[2])
    if kind == "index":
        return f"{expression(expr[1])}[{expression(expr[2])}]"
    if kind == "NOT":
        return f"!({expression(expr[1])})"
    if kind in {"GREATER_EQUAL", "GREATER"}:
        return expression(("LESS_EQUAL" if kind == "GREATER_EQUAL" else "LESS", expr[2], expr[1]))
    if kind in OPS:
        return f"({expression(expr[1])} {OPS[kind]} {expression(expr[2])})"
    if kind == "call_success":
        return "외부 호출 성공"
    return "분석된 조건값"


def variables(expr):
    if expr[0] == "variable":
        return {expr[1]}
    return set().union(*(variables(x) for x in expr[1:] if isinstance(x, tuple)))


def normalized(expr):
    """Comparison identity uses declarations/values, never displayed names."""
    if not isinstance(expr, tuple):
        return expr
    if expr[0] in {"GREATER_EQUAL", "GREATER"}:
        return normalized(("LESS_EQUAL" if expr[0] == "GREATER_EQUAL" else "LESS", expr[2], expr[1]))
    return tuple(normalized(x) for x in expr)


def node_key(node):
    ref = location(node)
    return (ref.get("function"), ref["line"])


def path_key(function, path):
    return (function,
            frozenset((normalized(g), node_key(n)) for g, n in path.guards if g[0] != "call_success"),
            tuple((normalized(loc), normalized(value), node_key(n)) for loc, value, n in path.writes),
            tuple((c['kind'], normalized(c['destination']), normalized(c['value']),
                   tuple(normalized(a) for a in c['arguments']), node_key(c['node']),
                   c.get('writes_before', len(path.writes))) for c in path.calls))


def path_claims(path, relevant_declarations=None, path_label="", initial=False):
    """One linked explanation per path, with call/write order preserved."""
    authority, conditions, effects, nodes = [], [], [], []
    for condition, node in path.guards:
        if condition[0] == "call_success":
            continue
        nodes.append(node)
        if condition[0] == "EQUAL" and ("builtin", "msg.sender") in condition[1:]:
            other = condition[2] if condition[1] == ("builtin", "msg.sender") else condition[1]
            authority.append(f"호출자가 `{expression(other)}` 주소와 일치")
        else:
            conditions.append(f"`{expression(condition)}`")

    def call_text(call):
        nodes.append(call['node'])
        amount = "" if call['value'] is None else f", ETH 지급액 `{expression(call['value'])}`"
        data = [expression(a) for a in call['arguments'] if a != ('constant', 'string', '')]
        payload = f", 호출 데이터 `{', '.join(data)}`" if data else ""
        return f"`{expression(call['destination'])}`에 `{call['kind']}` 실행{amount}{payload}"

    for index in range(len(path.writes) + 1):
        # Linear traces only permit writes before calls. Path traces retain the
        # exact write count at each call, including late-reset reentrancy cases.
        effects.extend(call_text(c) for c in path.calls if c.get('writes_before', len(path.writes)) == index)
        if index == len(path.writes):
            break
        loc, value, node = path.writes[index]
        if relevant_declarations is not None and (loc[0] != "variable" or loc[1] not in relevant_declarations):
            continue
        nodes.append(node)
        if value[0] in {"ADDITION", "SUBTRACTION"} and value[1] == loc:
            action = "증가" if value[0] == "ADDITION" else "차감"
            effects.append(f"`{expression(loc)}`에서 `{expression(value[2])}`만큼 {action}" if action == "차감"
                           else f"`{expression(loc)}`에 `{expression(value[2])}`만큼 증가")
        else:
            effects.append(f"`{expression(loc)}`에 `{expression(value)}` 기록")
    stages = []
    if authority:
        stages.append("권한: " + ", ".join(unique(authority)))
    if conditions:
        stages.append("성공 조건: " + " 및 ".join(unique(conditions)))
    if effects:
        stages.append(("초기 설정: " if initial else "상태 변화·외부 실행: ") + " → ".join(effects))
    return [claim(path_label + "; ".join(stages) + ".", nodes)] if stages else []


def explain(finding, contexts, details=(), kind=None):
    """Legacy rule summary + facts from relevant analyzed paths, not source scans.

The summary describes the rule's overall conclusion. Local claims are separately
bound to guards, writes and calls. Primary evidence order stays compatible.
"""
    primary = finding["evidence"]
    referenced = set()
    path_counts = {}
    for function, path in contexts:
        if not function.is_constructor and not function.is_constructor_variables:
            for expr, _ in path.guards:
                referenced.update(variables(expr))
            for loc, value, _ in path.writes:
                referenced.update(variables(loc) | variables(value))
    wanted = {(e.get("function"), e.get("line")) for e in primary}
    selected = []
    summary_claims = []
    # Each risk keeps its own evidence seed. Related guards and writes enrich
    # that seed without assigning another risk's unrelated function to it.
    reason_seeds = finding.get("_reason_evidence", [primary] * len(finding["reasons"]))
    kinds = finding.get("_reason_kinds", [kind] * len(finding["reasons"]))
    for text, seeds, category in zip(finding["reasons"], reason_seeds, kinds, strict=True):
        if not text.strip():
            continue
        if finding["verdict"] != "MALICIOUS":
            summary_claims.append((category, claim("안전 근거·사용자 영향: " + text), frozenset()))
            continue
        seed_keys = {(e.get("function"), e.get("line")) for e in seeds}
        refs = list(seeds)
        dependencies = set()
        anchors = set()
        for function, path in contexts:
            nodes = [n for _, _, n in path.writes] + [c["node"] for c in path.calls]
            candidates = nodes + [n for _, n in path.guards]
            if any(node_key(n) in seed_keys for n in candidates):
                refs.extend(n for _, n in path.guards)
                refs.extend(nodes)
                if not function.is_constructor and not function.is_constructor_variables:
                    anchors.update((node_key(n), normalized(loc)) for loc, _, n in path.writes)
                    anchors.update((node_key(c['node']), c['kind'], normalized(c['destination'])) for c in path.calls)
                for guard, _ in path.guards:
                    dependencies.update(variables(guard))
        for _, path in contexts:
            for loc, _, node in path.writes:
                root = loc
                while root[0] == "index":
                    root = root[1]
                if root[0] == "variable" and root[1] in dependencies:
                    refs.append(node)
                    refs.extend(n for _, n in path.guards)
        summary_claims.append((category, claim("판정 근거·사용자 영향: " + text, refs), frozenset(anchors)))
    for function, path in contexts:
        path_counts[function] = path_counts.get(function, 0) + 1
        nodes = [n for _, n in path.guards] + [n for _, _, n in path.writes] + [c["node"] for c in path.calls]
        relevant = finding["verdict"] == "BENIGN" or function.is_constructor or any(
            (location(n).get("function"), location(n).get("line")) in wanted for n in nodes)
        # Include control paths in risk explanations: the analyzed state writes
        # are evidence of authority, not an assertion that each path is harmful.
        control = bool(path.writes) and not path.calls and len(path.writes) == 1
        if relevant or control:
            count = sum(f == function for f, _ in contexts)
            label = f"{function.full_name}의 성공 경로 {path_counts[function]}: " if count > 1 else ""
            grouped = path_claims(path, referenced if function.is_constructor_variables else None, label,
                                  function.is_constructor or function.is_constructor_variables)
            selected.extend((path_key(function, path), c) for c in grouped)
    # Kept in memory between rule and verdict aggregation; never emitted as JSON.
    finding["_report"] = (summary_claims, selected, list(details))
    return finding


def contextual_result(verdict, reason, nodes, *, contexts, kind=None):
    return explain({"verdict": verdict, "reasons": [reason],
                    "evidence": unique([location(n) for n in nodes])}, contexts, kind=kind)


def merge_reports(findings):
    """Merge reports for ONE contract and verdict without changing detection.

    Only explicitly tagged risks with overlapping source actions can be merged
    across independent rules. Distinct branches within one rule stay separate.
    A successful BENIGN rule already proves the complete supported contract.
    """
    verdict = findings[0]['verdict']
    conclusions, paths, details, primary = [], {}, [], []
    for rule_index, finding in enumerate(findings):
        summaries, flows, extra = finding['_report']
        primary.extend(finding['evidence'])
        for kind, item, anchors in summaries:
            duplicate = next((old for old in conclusions if
                (verdict == 'BENIGN' or (kind is not None and old['kind'] == kind
                 and anchors and (anchors <= old['anchors'] or old['anchors'] <= anchors)))
                and rule_index not in old['rules']), None)
            if duplicate is None:
                conclusions.append(dict(kind=kind, claim=item, anchors=anchors, rules={rule_index}))
            else:
                duplicate['rules'].add(rule_index)
                duplicate['anchors'] |= anchors
                duplicate['claim'].evidence = unique(duplicate['claim'].evidence + item.evidence)
        for key, item in flows:
            paths.setdefault(key, item)
        details.extend(extra)
    return render(verdict, [c['claim'] for c in conclusions] + list(paths.values()) + details, primary)
