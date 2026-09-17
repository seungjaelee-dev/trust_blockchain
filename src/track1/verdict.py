"""독립 규칙의 결과를 계약/파일 단위로 모은다. 실패한 규칙은 안전 근거가 아니다."""
from pathlib import Path

from .rules import delegatecall, fixed_supply, supply, transfer_restrictions, expanded_tokens, expanded_vaults
from .rules.linear import Unsupported

RULES = (("공급량 상한", supply.analyze_contract),
         ("고정 공급량", fixed_supply.analyze_contract),
         ("비대칭 전송", transfer_restrictions.analyze_contract),
         ("임의 코드 실행", delegatecall.analyze_contract),
         ("확장 토큰 경로", expanded_tokens.analyze_contract),
         ("확장 금고 경로", expanded_vaults.analyze_contract))


def analyze(analysis, source):
    if any(Path(c.source_mapping.filename.absolute).resolve() != source.resolve() for c in analysis.contracts):
        return {"verdict": "UNCERTAIN", "reasons": ["import된 컨트랙트의 범위/원본 근거 위치는 아직 지원하지 않습니다."], "evidence": []}
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
                missing.append(f"{label}: {error}")
        if matched:
            findings.extend(matched)
        else:
            limitations.append(f"{contract.name}: " + " / ".join(missing))
    malicious = [f for f in findings if f["verdict"] == "MALICIOUS"]
    if malicious:
        return {"verdict": "MALICIOUS", "reasons": [r for f in malicious for r in f["reasons"]] + limitations,
                "evidence": [e for f in malicious for e in f["evidence"]]}
    if limitations or not findings:
        return {"verdict": "UNCERTAIN", "reasons": limitations or ["판정할 컨트랙트가 없습니다."], "evidence": []}
    return {"verdict": "BENIGN", "reasons": [r for f in findings for r in f["reasons"]],
            "evidence": [e for f in findings for e in f["evidence"]]}
