# 현재 진행 기록

2026-09-18 KST. 목표 제출일 9/20까지 달력 기준 2일, 공식 마감 시각은 미확인입니다.
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
- 의존성 고정·라이선스 고지·오프라인 패키징. 현재는 설치된 WSL 환경에 의존.
- 네트워크 차단과 자원 제한을 함께 적용한 깨끗한 실행, 혼합/대형 입력 검증.
- 중복 evidence와 파일별 구체적 근거 문구 개선, 제출 자료 작성.
- 웹·배포 패키지·독립 비공개 평가 성능은 아직 없음. 다음 계획은 PLAN.md.

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
- README의 파일 안내에 HTML 설명서 링크 추가.
- 문서는 이해 보조 자료이며, 사용자가 내용을 직접 설명해 본 상태는 아직 확인하지 않음.
