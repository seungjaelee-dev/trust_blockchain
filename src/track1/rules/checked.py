"""Do not discard checked arithmetic that can stop a seemingly dangerous path."""


def affine(expr):
    if expr[0] == "constant" and expr[1] == "uint256":
        return {}, expr[2]
    if expr[0] in {"ADDITION", "SUBTRACTION"}:
        left, a = affine(expr[1])
        right, b = affine(expr[2])
        sign = 1 if expr[0] == "ADDITION" else -1
        terms = dict(left)
        for term, coefficient in right.items():
            terms[term] = terms.get(term, 0) + sign * coefficient
            if terms[term] == 0:
                del terms[term]
        return terms, a + sign * b
    return {expr: 1}, 0


def contains(tree, expr):
    return tree == expr or any(contains(child, expr) for child in tree[1:] if isinstance(child, tuple))


def validate_checked(expressions, guards, writes):
    """Return a limitation, never silently drop an implicit success constraint."""
    used = [g for g, _ in guards] + [value for _, value, _ in writes]
    for expr, _ in expressions:
        terms, constant = affine(expr)
        if not terms:
            if not 0 <= constant < 2**256:
                return "checked 산술이 항상 실패하는 경로의 실행 가능성을 확정할 수 없습니다."
            continue
        if not any(contains(value, expr) for value in used):
            return "결과에 쓰이지 않는 checked 산술도 실행을 취소할 수 있어 경로를 보류합니다."
    return None
