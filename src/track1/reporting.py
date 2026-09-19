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


def path_claims(path, relevant_declarations=None, path_label=""):
    """Keep each fact tied to its own node; branch polarity comes from the path."""
    claims = []
    for condition, node in path.guards:
        if condition[0] == "call_success":
            continue
        text = f"분석한 성공 경로의 조건: `{expression(condition)}`."
        if condition[0] == "EQUAL" and ("builtin", "msg.sender") in condition[1:]:
            other = condition[2] if condition[1] == ("builtin", "msg.sender") else condition[1]
            text = f"호출자가 `{expression(other)}`와 같은 주소일 때만 이 경로로 진입할 수 있습니다."
        claims.append(claim(path_label + text, [node]))
    for loc, value, node in path.writes:
        if relevant_declarations is not None and (loc[0] != "variable" or loc[1] not in relevant_declarations):
            continue
        if value[0] in {"ADDITION", "SUBTRACTION"} and value[1] == loc:
            action = "증가" if value[0] == "ADDITION" else "차감"
            text = f"`{expression(loc)}`를 `{expression(value[2])}`만큼 {action}합니다."
        else:
            text = f"상태 변경: `{expression(loc)}`에 `{expression(value)}`를 기록합니다."
        claims.append(claim(path_label + text, [node]))
    for call in path.calls:
        amount = "" if call["value"] is None else f", ETH 지급액 `{expression(call['value'])}`"
        claims.append(claim(path_label + f"외부 실행: 대상 `{expression(call['destination'])}`에 `{call['kind']}`를 수행합니다{amount}.", [call["node"]]))
    return claims


def explain(finding, contexts, details=()):
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
    for text, seeds in zip(finding["reasons"], reason_seeds):
        if not text.strip():
            continue
        if finding["verdict"] != "MALICIOUS":
            summary_claims.append(claim(text))
            continue
        seed_keys = {(e.get("function"), e.get("line")) for e in seeds}
        refs = list(seeds)
        dependencies = set()
        for _, path in contexts:
            nodes = [n for _, _, n in path.writes] + [c["node"] for c in path.calls]
            if any((location(n).get("function"), location(n)["line"]) in seed_keys for n in nodes):
                refs.extend(n for _, n in path.guards)
                refs.extend(nodes)
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
        summary_claims.append(claim(text, refs))
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
            selected.extend(path_claims(path, referenced if function.is_constructor_variables else None, label))
    return render(finding["verdict"],
                  summary_claims + list(details) + selected,
                  primary)


def contextual_result(verdict, reason, nodes, *, contexts):
    return explain({"verdict": verdict, "reasons": [reason],
                    "evidence": unique([location(n) for n in nodes])}, contexts)
