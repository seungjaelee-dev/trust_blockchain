# 정상·위험 개발 문제

2026-09-17 사용자가 AI의 기대 판정 검토·문제 생성·실행·수정 사이클을 명시적으로 위임했다.
`tests/build_variants.py`가 원본 MIT 고지를 보존하며 별도 사본을 생성했다.
라벨과 근거는 `expected.json`에만 있으며, 분석 패키지는 이를 읽지 않는다.

40개: BENIGN 24개 / MALICIOUS 16개. 각 문제의 근본 이유는 expected.json에 있다.
원본/의미 변경 변형/의미 보존 사본을 독립 평가셋으로 혼동하지 않는다.
정상·위험 차이는 주석이나 이름이 아니라 검사·권한·상태 변경·자산 귀속의 차이다.

주의할 경계:
- `ownership_risk`: 무단 owner 변경과 별개로, 관리자 seize 자체도 대회에서 자산 탈취 경로다.
- `late_checked_safe`: 이 단일 장부 구조에서만 지급분의 checked 차감이 초과 지급을 취소한다.
  일반적인 외부 호출 후 상태 변경이 모두 안전하다는 뜻이 아니다.
- `delegate_no_deposit_safe` / `force_send_safe`: 대회의 특별한 force-send 자산 귀속 가정을 적용한다.
- `reentry_locked_safe`: 같은 출금의 실제 bool 잠금을 확인한다. 다른 무잠금 출금 함수를 붙인 경우는
  별도 회귀 테스트에서 UNCERTAIN을 요구한다.

전체 실행과 결과 해설: `docs/EXPANDED_RULES.md`.
