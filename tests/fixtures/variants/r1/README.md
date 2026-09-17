# R1 의미 변경 실습용 사본

원본: reference/public/P4_CappedMint.sol (MIT). 원본은 수정하지 않았다.
AI가 변형을 제안하고 의미상 정답을 설명했다. 사용자가 해당 테스트 진행 순서에 동의하고
P2/P4 작업을 요청한 후 2026-09-17 실행했다. 두 사례를 tests/test_supply.py에 포함했다.

| 파일 | 변경 | 의미상 정답 | 실제 출력 |
| --- | --- | --- | --- |
| cap_removed.sol | 공급량 상한 require만 제거 | MALICIOUS: 소유자가 상한 없이 반복 발행 가능 | MALICIOUS |
| cap_bypass.sol | bool 입력 checkCap이 true일 때만 상한 검사 | MALICIOUS: false로 호출하면 상한 우회 가능 | MALICIOUS: 9/17 경로 확장 후 탐지 (초기에는 UNCERTAIN) |

기존 정상 라벨과 상한 설명 주석은 혼동 방지를 위해 제거했다. SPDX MIT 고지는 유지했다.
실습: 두 파일에서 `totalSupply += amount`에 도달하기 위해 꼭 거쳐야 하는 검사가
무엇인지 비교한다. 의미상 정답과 분석기의 보류를 같은 것으로 취급하지 않는다.

재실행 명령:

```bash
python scripts/analyze.py tests/fixtures/variants/r1
```
