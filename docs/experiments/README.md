# 실험 기록

분석 패키지는 이 폴더의 정답/결과를 읽지 않습니다. 공개·개발 변형의 검증 근거이며 비공개 성능이 아닙니다.

현재 제출 정리본의 결과는 [submission-check.json](submission-check.json), 실제 출력은 [submission-integration.json](submission-integration.json)에 있습니다. 아래 stage1/flow 기록은 철회 전 코드를 포함한 과거 실험입니다.

그 뒤 수행한 [최종 교차검증](release-crosscheck.json)은 Git 제출 후보147개만 새 폴더에 복사한 뒤 캐시 없이 빌드한 결과입니다. 전체31 테스트248.133초, 혼합60개83.554초, 별도 경로의 이름·주석·줄 위치 변형 및 문법 오류6개 검사를 통과했습니다. 채점 실행은 모두 네트워크 차단·2CPU/4GB·추가swap없음이며, 빌드 준비 단계는 온라인입니다. 후보 파일과 이미지 해시를 기록했으며 원격 clone·commit·push 완료 기록은 아닙니다.

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

## 함수별 흐름 설명 검증 (9/19)

- [혼합60개 출력](flow-integration.json) · [실행 정보·이미지·코드 해시](flow-snapshot.json).
- 이미지 `trust404-track1:flow-review`, 네트워크차단·2CPU/4GB·추가swap없음: 65.284초. 기존 reporting-integration과 판정60개동일, schema·위치 대응·중복 근거 없음·오류 격리 통과.
- 공개5개 이유 수: 17/8/14/13/6 → 5/3/4/5/4. 같은 발견의 결론과 경로 사실을 묶었으며 임의 개수 제한을 적용하지 않았다.
- 전체37 테스트 통과(381.354초). 전체 실행 시작 후 별도 작업에서 추가된 기본 시간 예산 테스트1개도 후속 통과(0.022초). 단일 실행에서38개 통과한 기록은 아니다.
- 최초 출력 테스트1개는 ‘16행’ 단독 표기를 가정해 실패했다. 함수 흐름으로 묶인 ‘15, 16, 17, 18행’에서도 상한 검사16행을 확인하도록 검증식을 변경한 뒤 전체 통과.
- 서로 다른 위험3개(같은 종류의 독립 함수2개 포함), 여러 컨트랙트, 분기 극성, 이름/Unicode 위치 이동, 외부 호출과 장부 초기화 순서를 검증했다.
- 최종 이미지의 src 해시와 작업 트리의 src 해시가 일치함을 확인했다. 작업 시작 전 이미 존재하던 stage1 규칙 확장과 별도 시간 제한 변경을 포함하는 현재 작업 트리의 검증이며, 이 설명 정리 작업 자체는 탐지 조건을 바꾸지 않았다.
- 실행 시간은 환경·캐시 차이가 있어 이전 수치 대비 속도 개선을 주장하지 않는다. 개발 표본이며 비공개 일반화 점수가 아니다.

```bash
docker build --platform linux/amd64 -t trust404-track1:flow-review .
python tests/evaluate_ledger_docker.py --image trust404-track1:flow-review \
  --output flow-integration \
  --reporting-baseline docs/experiments/reporting-integration.json
```

## 지원 확대 1단계 검증 (9/19)

**철회 전 기록:** 합성300개 동일 조건 비교에서 두 버전 모두 정답40/오답5/보류255, 변경0개였다. 사용자 요청으로 1단계 탐지 확장과 전용 테스트/실행 스크립트를 제거했다. 아래 수치와 이미지 기록은 현재 지원 범위가 아닌 실험 이력이다.

- [10파일 변경 전후 비교](stage1-integration.json): 네트워크차단/2CPU/4GB, 기존 보류8 → 보류1. 최종 정상3/악성6/보류1,16.421초. 독립 비공개 평가가 아닌 직접 작성한 개발셋이다.
- [고정 이미지 전체 회귀](stage1-suite.json):38개 전부통과,247.216초. 새52개 Solidity 입력과 시간 예산 검사를 포함한다.
- 최종 검증은 소스·테스트를 이미지에 고정하여 동시 편집의 영향을 분리했다. 기록된 이미지 내부 파일과 당시 작업 트리의 해시가 일치한다.
- 재현: 설치된 개발 Python에서 `python tests/evaluate_stage1_docker.py --image trust404-track1:stage1-review`. 상세 구현 경계와 빌드 조건은 [STAGE1.md](../STAGE1.md).

## 제출 정리본 검증 (9/19)

- [검증 명세](submission-check.json) · [혼합60개 실제 출력](submission-integration.json).
- 이미지 `trust404-track1:submission-review`, 기본 Dockerfile로 빌드. 현재 철회 후 코드·고지 포함. 전체31 테스트198.769초, 혼합60개38.276초로 통과.
- 네트워크 차단·2CPU/4GB·추가swap없음. 혼합 입력의 기대 판정, 원본 schema, 이유와 위치 대응, 문법 오류 격리, PermissionError 없음 확인. 개발 자료이며 비공개 정확도나 이전 측정 대비 속도 개선을 뜻하지 않음.
- 전체 테스트는 이미지의 src를 고정하고 tests/reference를 읽기 전용으로 연결. 테스트 전후 해시 동일. Docker 진입점을 우회하는 테스트에는 별도 임시 HOME과 bundled solc 별칭이 필요하며, 초기 실패와 최종 재실행 조건도 명세에 기록. 재현 방법은 [DOCKER](../DOCKER.md)의 개발용 회귀 절차.
- 고지 원문 해시와 설치 패키지54개 버전 일치 확인. 원시 로그는 results/ 아래에만 보존하고 Git에서 제외.
