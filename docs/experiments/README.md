# 실험 기록

분석 패키지는 이 폴더의 정답/결과를 읽지 않습니다. 공개·개발 변형의 검증 근거이며 비공개 성능이 아닙니다.

| 파일 | 내용 |
| --- | --- |
| [expanded-baseline.json](expanded-baseline.json) | 확장 전 최초29개 개발 문제의 출력 |
| [expanded-results.json](expanded-results.json) | 9/17 확장 후 개발40개 판정·이유·근거 |
| [slither-baseline.json](slither-baseline.json) | 대표10개에 대한 기본 Slither detector 경고 |
| [experiment-snapshot.json](experiment-snapshot.json) | 9/17 검증 당시 코드/문제 SHA256과 실행 정보 |

snapshot은 당시 파일 경로의 역사적 기록입니다. 9/18 정리로 일회성 API 관찰 도구는 삭제되고
실험 JSON은 이 폴더로 이동했습니다. 이를 현재 전체 작업 트리와 동일한 고정본이라고 주장하지 않습니다.
당시 미지원 범위와 수정 이력은 [분석 설명](../EXPANDED_RULES.md)에 있습니다.

9/18 사용자 자원 제한 실행 원본은 로컬 `results/limited.json`·`limited.log`에 보존했습니다.
사용자 보고: CPU2, RAM3.8Gi, Swap0, real28.704초. 네트워크 차단 검증은 아직 아닙니다.

재실행:

```bash
python tests/evaluate_variants.py my-run
python scripts/compare_baseline.py
```

첫 명령은 results/에 새 결과를 저장하고, 두 번째는 이 폴더의 slither-baseline.json과
results/baseline/의 상세 결과를 갱신합니다.

## 장부 규칙 비교 실험 (9/19)

- 기존 `trust404-track1:homefix` 이미지와 새 규칙을 동일한 대표14개에 비교.
- 기존 14개 전부 보류 → 새 규칙 정상6·위험5·보류3. 이는 선별한 개발 사례이며 300개 전체 정확도가 아니다.
- U009의 관리자 예외는 대회 기준상 위험, M009/M016의 피해 자산 도달/전송 가능성은 보류로 검토했다. 원본 라벨을 변경하지 않았다.
- 최종 이미지는 공개5 + 기존 개발40 + 대표14 + 문법 오류1을 섞은 60개로 오프라인 2CPU/4GB 실행을 검증한다.
- 재현: `docker build --platform linux/amd64 -t trust404-track1:ledger-review .` 후 WSL 개발 Python으로 `python tests/evaluate_ledger_docker.py`.
- [장부 검증 스냅샷](ledger-snapshot.json), [최종 혼합 출력](ledger-integration.json), [기존 대표14 출력](ledger-baseline.json).
- 입력 소스와 규칙 해시를 스냅샷에 보존한다. 300개 전체 재실행/독립 평가/실제 EVM 공격 실험은 수행하지 않았다.

## 이유·위치 연결 검증 (9/19)

- [새 혼합 출력](reporting-integration.json) · [이미지와 코드/입력 해시](reporting-snapshot.json).
- `trust404-track1:reporting-review`, `--network none`, 2CPU/4GB, 추가 swap 없음: 60개 94.622초.
- 기존 장부 통합 출력과 60개 판정이 모두 같다. 원본 schema, 이유 앞 위치와 evidence의 대응, 줄 범위, 위치/문구 완전 중복 제거, 오류 격리, PermissionError 없음 확인.
- 함수·변수 이름과 Unicode 주석/줄 이동, 서로 다른 분기, 권한·상한 검사, 미지원 연산의 실제 위치를 회귀 검사한다. 위치 대응 검사는 모든 설명의 의미적 정확성을 자동 증명하는 것은 아니다.
- 기존 3초 timeout 회귀는 Slither 초기화 중 제한에 걸려 가짜 컴파일러 시작을 확인하지 못했다. 테스트만 10초로 조정해 60초 대기하는 컴파일러/자식의 실제 종료를 검사한다. 프로그램의 기본 시간 제한은 변경하지 않았다.
- 전체26개 실행에서25개 통과·위 timeout1개 실패 후, 수정한 timeout와 추가한 다중위험 테스트2개가 순차 재실행에서 모두 통과했다. 최종27개 항목을 나누어 검증했으며 수정 후 전체 재실행 결과로 표기하지 않는다.

WSL 개발 환경에서 재현:

```bash
docker build --platform linux/amd64 -t trust404-track1:reporting-review .
python tests/evaluate_ledger_docker.py --image trust404-track1:reporting-review \
  --output reporting-integration \
  --reporting-baseline docs/experiments/ledger-integration.json
python -m unittest discover -s tests -p test_reporting.py -v
```

개발 환경의 Python 의존성은 필요하다. 제출용 이미지 자체 분석은 README의 Docker run만으로 실행한다.
