# 추가 반례: 사용자 정답 검토 대기

**2026-09-17 낮 갱신:** 사용자가 기대 판정 검토·실행·수정을 AI에 위임하여 세 파일을 실제 실행했다.
결과: missing_allowance MALICIOUS / no_sender_restriction BENIGN / no_deposit BENIGN.
사용자 본인의 코드 검토/이해 완료를 뜻하지 않는다. 아래는 생성 당시의 이력이다.

2026-09-17. 원본 MIT 샘플의 별도 사본이며 SPDX 고지는 보존했다.
원본의 LABEL과 설명 주석은 제거했다. **아직 컴파일/분석 테스트를 실행하지 않았다.**
사용자에게 기대 결과 검토 질문을 보냈으나 이번 기록 시점에 응답이 없다.

| 파일 | 변경과 사람이 검토할 의미 | 현재 분석기의 예상 반응 (미실행) |
| --- | --- | --- |
| missing_allowance.sol | P1의 대리 전송에서 allowance 검사와 차감을 둘 다 제거. 남의 잔액이 충분하면 임의 전송할 수 있으므로 의미상 MALICIOUS 제안 | UNCERTAIN: 안전 대리전송 패턴에 맞지 않음. 이 탈취 탐지 규칙은 미구현 |
| no_sender_restriction.sol | P3의 whitelist[msg.sender] require만 제거. 남은 목록 setter는 전송에 영향을 주지 않으므로 기존 비대칭 위험은 사라짐 | UNCERTAIN: 잔여 setter까지 정상이라고 검증하는 범위는 미지원 |
| no_deposit.sol | P5의 payable deposit 함수를 제거. 강제 송금 ETH를 사용자 자산으로 보지 않는 대회 가정 아래 기존 예치금 근거로 MALICIOUS를 내면 안 됨 | UNCERTAIN: 사용자 예치 경로를 확인할 수 없음 |

실제 정답과 현재 지원 범위의 예상 출력을 구분한다. UNCERTAIN은 악성 탐지 성공이 아니다.
정답 검토 후 이 폴더를 실행하고 결과를 회귀 테스트에 추가할 예정이다.
