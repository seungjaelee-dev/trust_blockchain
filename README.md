# TRUST404 Track 1 — 시작 지침 패키지

상태: 학습용 단일 파일 구조 출력 도구를 추가했습니다. 자동 판정기·제출용 JSON CLI·웹은 아직 없습니다.
2026-09-16 기준, 1인 하루 3시간, 9/20 제출을 목표로 합니다.
이 폴더는 이전 Track 3 프로젝트와 별개의 새 프로젝트입니다.

## 제품

아래 제품 구조는 목표 설계이며, 현재 실행 가능한 범위는 다음 학습용 도구입니다.

## 현재 실행: Solidity 구조 확인

Ubuntu-24.04의 Python 3.12.3 / Slither 0.11.6 환경을 사용합니다.
프로젝트 소스는 Windows 폴더, Python 가상환경은 Ubuntu 홈에 있습니다.

```bash
source ~/.venvs/trust1/bin/activate
cd "/mnt/c/Users/seung/OneDrive/바탕 화면/Project/trust1"
SOLC_VERSION=0.8.20 python scripts/inspect_sol.py reference/public/P2_HiddenMint.sol
SOLC_VERSION=0.8.20 python scripts/inspect_sol.py reference/public/P4_CappedMint.sol
```

`inspect_file`은 Slither로 파일을 읽고 함수/modifier를 순회합니다.
`SOLC_VERSION=0.8.20`은 해당 명령에서 사용할 컴파일러를 지정합니다.
9/16 점검 당시 기본 버전은 0.8.37이었으며, 0.8.20을 추가 설치해 위 명령으로 검증했습니다.
`print_nodes`는 원본 줄 위치, 노드 종류, 식을 표시합니다.
함수에 붙은 modifier 목록과 modifier 정의를 연결해서 읽으세요.
출력 순서는 실행 순서의 증명이 아닙니다. Slither의 내부 초기화 항목도 별도로 표시합니다.
파일명/함수명은 표시용이며 이름이나 출력 문자열로 판정하는 규칙은 없습니다.

이 도구는 사람이 읽는 구조를 stdout으로 출력합니다. 대회 JSON 스키마를 따르는 CLI가 아니며,
단일 파일만 받습니다. 성공 종료 코드는 0, 잘못된 경로는 2, 컴파일/분석 실패는 1입니다.
파일별 격리/시간 제한/오프라인 패키징은 아직 구현되지 않았습니다.

실패 입력을 직접 확인할 수 있습니다.

```bash
SOLC_VERSION=0.8.20 python scripts/inspect_sol.py tests/fixtures/errors/invalid_syntax.sol
echo $?
```

문법 오류와 종료 코드 1이 예상됩니다. 원본 public 샘플은 수정하지 않습니다.

## 목표 제품 흐름

사용자는 .sol 파일 또는 폴더를 전달합니다. 프로그램은 코드를 로컬에서 구조화하고,
권한·조건·상태 변경을 분석해 MALICIOUS/BENIGN/UNCERTAIN과 근거를 출력합니다.
웹은 동일 분석기의 업로드·코드 위치 표시 화면입니다. CLI가 자동 채점의 핵심입니다.

| 단계 | 입력 → 출력 | 담당 |
| --- | --- | --- |
| 진입점 | 폴더/웹 업로드 → 파일 목록 | 우리 코드 |
| 구조 분석 | 소스 → 함수·변수·실행 경로·IR | solc + Slither |
| 근거 수집 | 구조 → 권한·발행·전송 제한·호출 사실 | 우리 분석 규칙 |
| 판정 | 근거 + 미지원 범위 → verdict/reasons/evidence | 우리 판정 계층 |
| 표현 | 결과 → JSON/웹 보고서 | 우리 CLI/웹 |

개발 중 Codex는 코드를 작성·설명합니다. 채점 중 분석기는 Codex/인터넷에 질문하지 않습니다.
컴파일러와 의존성은 미리 준비해야 합니다. 소스를 컴파일하는 것과 배포/자산 전송은 다릅니다.

## 시작

1. 새 폴더를 WSL 안에 만들고 이 패키지를 풉니다. AGENTS.md가 프로젝트 루트에 있어야 합니다.
2. VS Code WSL 터미널에서 해당 폴더를 열고 Codex CLI를 실행합니다.
3. FIRST_TASK.md의 첫 작업 프롬프트를 붙여 넣습니다.
4. 첫 단계는 P2/P4의 실제 코드 구조 출력과 CLI 계약까지입니다. 완성된 악성 분석기라고 부르지 않습니다.
5. 이후 docs/PROGRESS.md를 읽고 다음 단계를 이어갑니다.

기존 Track 3 폴더 아래에 넣지 마세요. 기존 AGENTS.md 지침이 상속될 수 있습니다.
설치/로그인 상태가 미확인이라면 공식 Codex 안내와 로컬 오류부터 확인합니다.
Windows와 WSL의 Python/가상환경을 혼용하지 않습니다.

## 구성

- AGENTS.md: Codex의 지속 작업 지침, 사용자 배경, 학습법, 심사 조건.
- FIRST_TASK.md: 첫 세션의 구체적인 실행 요청.
- docs/PLAN.md: 구현 범위·참고 GitHub·일정·완료 기준.
- docs/PROGRESS.md: 현재 상태와 다음 작업.
- reference/TRACK1_README.md: 첨부한 README 원문을 내용 변경 없이 복사.
- reference/schema.json: 첨부한 출력 규격 원본.
- reference/public/: 첨부한 Solidity 5개 원본, 수정 금지.

## 연구실·학습 맥락

사용자는 Python/C 및 pandas·ML 이상거래탐지 경험을 보유하며 Solidity는 입문 단계입니다.
문법을 전부 먼저 배우기보다 코드 흐름을 따라 필요한 문법을 익힙니다.
Hardware Security Lab 홈페이지는 안전한 지갑·이상거래탐지 등을 연구 분야로 소개합니다.
본 프로젝트는 보안 분석/코드 이해/재현 실험 경험으로 연결하는 제안이며,
해당 연구실의 채용·교수 개인의 평가·인턴 합격을 보장하지 않습니다.
https://sites.google.com/view/hwseclab/

## 제출 전

- 최신 공통 제출 안내와 오프라인 설치/실행 환경 확인.
- 실제 네트워크 차단 환경에서 runtime·solc·라이브러리를 포함한 실행 검증.
- JSON 스키마 검증, 일부 실패 처리, 제한 시간 내 종료.
- 공개 샘플과 검토한 변형셋의 결과·오탐·미탐·미지원 범위.
- 실행 README, 출처/라이선스 고지, AI 활용/본인 기여, 영상·피치덱·GitHub.

여기에 적힌 실행 파일과 기능은 계획입니다. 구현한 후 실제 명령·버전·검증 기록으로 갱신합니다.
