# 현재 진행 기록

2026-09-19 KST. 목표 제출일 9/20까지 달력 기준 1일, 공식 마감 시각은 미확인입니다.
이전 세션 상세 기록은 [9/15~17 이력](history/2026-09-15_17.md)에 보존했습니다.

## 완료와 근거

- 폴더 JSON CLI, 파일별 컴파일/실패 격리, 파일당 기본30초/전체540초, 자식 프로세스 종료 구현.
- 기존 네 규칙과 확장 토큰/금고 규칙 구현. 제한된 분기/내부 호출/상속과 지원 한계는 EXPANDED_RULES.md 참고.
- 9/17 공개5·개발40(정상24/위험16)·의미 보존40 판정 일치.
- 9/17 회귀17개, 63.937초, OK. schema/오류/timeout/미지원 경계 포함.
- 기본 Slither detector를 대표10개에 실행해 비교. 결과는 experiments/에 보존.
- 새 의존성 설치나 upstream 소스 복사 없이 기존 Slither API를 사용.

## 9/18 사용자 자원 제한 시험

- 사용자가 WSL 설정 및 CLI 실행을 직접 수행하고 터미널 결과를 대화에 제공.
- nproc=2, RAM=3.8Gi, Swap=0B. 개발40 분석 real=28.704초.
- 전달된 JSON은 정상24/위험16으로 기대 판정과 일치. results/limited.json·limited.log 보존.
- 이는 사용자 보고 및 제공된 결과에 근거한 기록. 깨끗한 오프라인 재현/비공개셋 성능/일반 부하 보장은 아님.
- 사용자의 CLI 실행은 확인했으나 모든 판정 규칙의 이해/변형 실습 완료는 아직 확인하지 않음.

## 남은 일

- 제출 OS/아키텍처·Docker 반입·용량/제출 경로 확인.
- 최종 이미지 전달 검증과 라이선스 고지 정리. Docker 의존성 고정·빌드·공개 표본 실행 완료.
- 최종 Docker 환경의 혼합 오류/대형 입력 검증.
- 중복 evidence와 파일별 구체적 근거 문구 개선, 제출 자료 작성.
- 웹·독립 비공개 평가 성능은 아직 없음. 다음 계획은 PLAN.md.

## 9/18 디렉터리·문서 정리

- 사용자 요청: 불필요한 문서/파일 정리, README와 현재 상태 갱신.
- README를 현재 WSL 실행법·검증·범위·구조·제출 미완료 항목 중심으로 재작성.
- PLAN의 지난 일정/미구현 가상 파일 목록을 제거하고 남은 제출 작업으로 정리.
- 초기 문서 FIRST_TASK.md, docs/R1.md, docs/WORKER_FLOW.md의 중복 안내는 EXPANDED_RULES.md로 통합 후 삭제.
- 일회성 API 관찰 도구 scripts/inspect_paths_api.py와 중간 cycle1/cycle2 결과·로그 삭제.
  재사용 가능한 inspect_sol.py/inspect_ir.py, 회귀 테스트, 원본 표본, 사용자 limited 결과는 보존.
- 실험 JSON4개를 docs/experiments/로 이동. 이전 snapshot은 9/17 당시 경로/해시를 나타내는 이력으로 유지.
- 긴 과거 PROGRESS는 history/에 보존. 당시 문서/도구 경로는 현재와 다를 수 있음.
- 판정 로직/CLI 계약/테스트 입력은 변경하지 않음. 실험 비교 스크립트의 저장 경로만 새 위치로 맞춤.
- 검증: 현재 문서의 로컬 링크 정상, 실험 JSON4개 읽기 정상, 남긴 스크립트4개 Python AST 구문 통과. 이동된 저장 폴더 확인 및 원본 reference Git diff 없음. limited.json 40개를 기대 정답과 기계적으로 재비교해 일치 확인. 분석 로직 변경이 없어 전체 회귀17개는 재실행하지 않음.
- 다음 사용자 실습: EXPANDED_RULES.md의 cap_branch 정상/위험 한 쌍을 비교하고 우회 경로를 설명.

## 9/18 구조 이해 HTML 추가

- 사용자 요청: AI로 작성된 전체 코드 흐름을 본인이 이해하고 심사위원에게 설명할 수 있도록, 기초부터 설명하는 HTML 문서 작성.
- `docs/project-flow-guide.html` 추가. 탭 구조로 문제 기초, 실행 흐름, 폴더 지도, 판정 규칙, 심사 답변, 말로 설명 연습을 정리.
- 실제 호출 흐름은 `scripts/analyze.py` → `src/track1/cli.py` → `src/track1/worker.py` → Slither/solc → `src/track1/verdict.py` → `src/track1/rules/*.py` → stdout JSON으로 설명.
- 사용자 추가 요청에 따라 Python import/subprocess 흐름, worker와 Slither 연결, `verdict.py`의 `RULES` 호출 구조, 복수 위험 사유의 JSON 집계 방식을 코드 예시와 함께 보강.
- 이어서 입력 폴더 인자 → `.sol` 파일 필터링 → 기본 `UNCERTAIN` 결과 리스트 → for문 분석 → worker subprocess → Slither 분석 객체 → rules 호출 → JSON 배열 출력의 전체 로직을 8단계 코드 흐름으로 추가.
- `src/track1/rules/`의 각 파일이 직접 판정 규칙인지 보조 해석기인지, 어떤 위험/오류를 잡기 위한 파일인지, 핵심 함수가 무엇인지 표로 추가. Slither/solc가 제공하는 구조 분석과 프로젝트 자체 판정 로직의 경계도 설명.
- README의 파일 안내에 HTML 설명서 링크 추가.
- 문서는 이해 보조 자료이며, 사용자가 내용을 직접 설명해 본 상태는 아직 확인하지 않음.

## 9/18 협업 후보 저장소 코드 비교

- 사용자 요청으로 yunu471/trust404-track01의 analyzer.py, README, run.sh, 검증 스크립트를 읽고 현재 CLI/worker/verdict/규칙 구조와 비교.
- 비교 대상 커밋: 2792b80a75dcb0b23f2c750575047322c4454730. 외부 코드를 실행하거나 분석기에 합치지는 않음. 성능 수치의 비교 실험은 수행하지 않음.
- 상대 구현은 Python 표준 라이브러리와 정규식/괄호 매칭을 사용하여 설치가 간단함. 현재 구현은 Slither/solc의 구조 정보와 제한된 경로 해석을 사용하며 오프라인 패키징이 남아 있음.
- 코드 검토상 상대 구현의 이름 의존, 상한 검사와 실제 증가량 연결 부재, 탐지 없음/개별 탐지 예외 이후 BENIGN 가능성, delegatecall 예치 경로 연결 부재를 확인.
- typ_immutable_check가 발견한 상태변수 타입에 immutable 문자열을 붙이는 문제와 전체 시간 예산 부재도 확인. 실행 재현 전이므로 실제 오탐 수나 정확도로 보고하지 않음.
- 협업 제안: 현재 구조 분석 기반을 유지하고 서로 만든 변형 문제로 교차 평가한 뒤, 실패 원인을 검토하여 규칙을 개선. 단순히 두 분석기의 MALICIOUS 결과를 합치는 방식은 피함.
- 다음 단계 후보는 동일 입력/정답으로 두 구현의 판정·근거·시간을 비교하는 교차 실험. 사용자의 규칙 이해 완료는 아직 확인하지 않음.

## 9/18 Docker 환경 준비

- 사용자에게 Docker 실행 허용을 확인받아 Dockerfile, .dockerignore, docker/requirements.lock,
  scripts/prepare_docker.py, docs/DOCKER.md를 추가. 분석 로직은 변경하지 않음.
- 실제 WSL의 Python 3.12.3 및 설치 패키지 51개의 버전을 기록. pip check 정상.
  Python 버전은 현재 개발 버전이며 대회 필수 버전이라고 확인된 것은 아님.
- Linux amd64 solc 0.8.20의 SHA256을 확인하고 artifacts/docker로 복사.
  준비 스크립트와 이미지 빌드 양쪽에서 같은 SHA256을 검사하도록 구성.
- 복사한 solc를 명시한 WSL CLI 실행 종료 코드 0, 공개5 판정 BENIGN/MALICIOUS/MALICIOUS/BENIGN/MALICIOUS 확인.
- 개발 시 src/scripts 읽기 전용 연결, 제출 시 소스 포함 이미지, 네트워크 차단·2CPU/4GB 실행,
  docker save/load와 이미지 tar 해시 기록 명령을 문서화.
- 현재 Windows 표준 설치 경로와 WSL에 Docker 실행 파일/소켓이 없어 이미지 build/run은 미검증.
  사용자에게 Docker 설치 상태를 질문. 설치 후 빌드·공개/변형/실패 입력 검증을 이어가야 함.
- 기본 이미지는 Python 정확한 버전 태그이며 digest 고정 전. 의존성은 버전 lock이며 배포 파일 해시 lock은 아님.
  최종 이미지 및 라이선스 고지/소스 제공 정리, 오프라인 전달 검증은 미완료.
- 사용자 Docker 실행 실습/이해 완료는 아직 확인하지 않음.

## 9/19 Docker 재현과 제출용 README 정리

- 이전 Dockerfile 수정으로 HOME=/home/trust1과 UID/GID 10001의 쓰기 권한을 설정. bundled solc와 판정 로직은 유지.
- 이전 실제 검증: Docker build 성공, --network none·2CPU/4GB 공개5 판정 일치, PermissionError 없음.
- 사용자 보고: 다른 디렉터리에서 clone한 뒤 Docker build/run과 환경 확인 정상. 별도 컴퓨터 검증으로 확대 해석하지 않음.
- README를 clone → build → offline run 중심의 제출용 대표 문서로 재작성. 개인 가상환경 경로 제거.
- JSON 계약·시간 예산·판정 원리·지원 한계·환경 버전·검증 기록·기여·이미지 save/load 절차 정리.
- DOCKER의 미검증/solc Git 제외 안내를 현재 상태로 수정하고 PLAN도 갱신.
- 이번 작업은 문서만 변경. 분석 테스트 재실행 및 새 혼합 오류 입력 검증은 하지 않음. 사용자는 혼합 오류 검증을 다음 날 진행 예정.
- 사용자의 Docker 재현 실행은 확인했으나 전체 규칙 이해 완료는 기록하지 않음.
- 다음: 최종 Docker 혼합 오류 검증, 배포 고지·이미지 전달·제출 형식 확인.
