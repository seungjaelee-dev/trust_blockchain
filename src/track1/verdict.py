"""독립 규칙의 결과를 계약/파일 단위로 모은다. 실패한 규칙은 안전 근거가 아니다."""
from pathlib import Path
import sys

from .rules import delegatecall, fixed_supply, supply, transfer_restrictions, expanded_tokens, expanded_vaults, ledger_operations
from .rules.linear import Unsupported
from .reporting import claim, render, unique

RULES = (("공급량 상한", supply.analyze_contract),
         ("고정 공급량", fixed_supply.analyze_contract),
         ("비대칭 전송", transfer_restrictions.analyze_contract),
         ("임의 코드 실행", delegatecall.analyze_contract),
         ("확장 토큰 경로", expanded_tokens.analyze_contract),
         ("확장 금고 경로", expanded_vaults.analyze_contract),
         ("장부 전송과 소각", ledger_operations.analyze_contract))


def analyze(analysis, source):
    if any(Path(c.source_mapping.filename.absolute).resolve() != source.resolve() for c in analysis.contracts):
        return render("UNCERTAIN", [claim("import된 컨트랙트의 범위/원본 근거 위치는 아직 지원하지 않습니다.", scope="입력 의존성 분석")])
    findings, limitations = [], []
    for contract in analysis.contracts:
        # Abstract bases are analyzed through each deployable descendant's resolved
        # functions/state. An abstract-only input remains UNCERTAIN below.
        if contract.is_abstract and any(not c.is_abstract and contract in c.inheritance for c in analysis.contracts):
            continue
        matched, missing = [], []
        for label, rule in RULES:
            try:
                matched.append(rule(contract))
            except Unsupported as error:
                missing.append((label, str(error), error.node))
        if matched:
            findings.extend(matched)
        else:
            for label, message, _ in missing:
                print(f"[{contract.name} / {label}] {message}", file=sys.stderr)
            # Localized failures first; otherwise present the broader path rules.
            # These are analyzer limitations, not proof that the code lacks a guard.
            selected = [m for m in missing if m[2] is not None] or missing[-3:]
            seen = set()
            for label, message, node in selected:
                if message in seen:
                    continue
                seen.add(message)
                limitations.append(claim(f"{label}의 분석 한계: {message} 이 한계는 위험이 없다는 뜻이 아닙니다.",
                                         [node] if node is not None else [],
                                         scope=f"컨트랙트 {contract.name} · 분석 범위"))
    malicious = [f for f in findings if f["verdict"] == "MALICIOUS"]
    if malicious:
        limited = render("UNCERTAIN", limitations)
        return {"verdict": "MALICIOUS", "reasons": unique([r for f in malicious for r in f["reasons"]] + limited["reasons"]),
                "evidence": unique([e for f in malicious for e in f["evidence"]] + limited["evidence"])}
    if limitations or not findings:
        return render("UNCERTAIN", limitations or [claim("판정할 컨트랙트가 없습니다.")])
    return {"verdict": "BENIGN", "reasons": unique([r for f in findings for r in f["reasons"]]),
            "evidence": unique([e for f in findings for e in f["evidence"]])}
