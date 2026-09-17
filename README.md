# TRUST404 Track 1 — 스마트 컨트랙트 위협 탐지

Solidity 소스의 코드 흐름과 권한·자산 변경을 분석하는 Python CLI입니다.
Slither/solc로 구조를 읽고 자체 규칙으로 `BENIGN`, `MALICIOUS`, `UNCERTAIN`과 근거 위치를 출력합니다.
파일명·주석 라벨·외부 API·LLM을 판정에 사용하지 않습니다.

**현재 상태:** 개발용 CLI와 테스트 구현 완료. 오프라인 제출 패키징은 준비 중입니다.
이 README의 명령은 이미 의존성을 설치한 WSL 개발 환경용이며, 새 컴퓨터의 설치 방법은 아직 완성되지 않았습니다.

## 실행

Windows PowerShell에서 WSL로 진입합니다.

```powershell
wsl -d Ubuntu-24.04
```

WSL에서 프로젝트 폴더로 이동하고 기존 가상환경을 켭니다.

```bash
cd "/mnt/c/Users/seung/OneDrive/바탕 화면/Project/trust1"
source ~/.venvs/trust1/bin/activate
python scripts/analyze.py reference/public
```

다른 폴더를 분석할 때는 마지막 인자를 입력 디렉터리로 바꾸세요.
바로 아래의 `.sol` 파일을 모두 처리하며 하위 폴더는 재귀 탐색하지 않습니다.

```bash
mkdir -p results
python scripts/analyze.py tests/fixtures/variants/expanded \
  > results/analysis.json 2> results/analysis.log
```

- stdout: 파일별 결과가 담긴 JSON 배열 하나. stderr: 진행 상황과 진단 로그.
- 결과 항목: `file`, `verdict`, `reasons`, `evidence`. 위험 판정에는 함수/줄 근거가 포함됩니다.
- 일부 파일 실패·시간 초과: 해당 파일은 `UNCERTAIN`, 다른 파일은 계속 처리하고 종료 코드 0.
- 입력 폴더 없음/빈 폴더: stderr로 알리고 종료 코드 2. 가짜 결과를 만들지 않습니다.
- 파일별 기본 제한 30초, 전체 예산 최대 540초. `--file-timeout`, `--total-timeout`으로 조정합니다.

검증 환경은 Ubuntu-24.04, Python 3.12.3, Slither 0.11.6, crytic-compile 0.4.2, solc 0.8.20입니다.
기본 solc 경로는 `~/.solc-select/artifacts/solc-0.8.20/solc-0.8.20`입니다.
다른 설치 경로는 `--solc /absolute/path/to/solc`로 지정합니다. 실행 중 설치/다운로드하지 않습니다.

## 검증

```bash
# 개발 문제 40개의 기대 판정과 비교하고 results/에 실행 결과 저장
python tests/evaluate_variants.py my-run

# 공개 표본, 변형, JSON 계약, 실패 격리, 시간 제한 회귀
python -m unittest discover -s tests -v
```

테스트에는 `requirements-dev.txt`의 jsonschema가 필요합니다.

| 항목 | 확인 결과 |
| --- | --- |
| 공개 표본 | 5/5 기대 판정 일치 |
| 개발 문제 | 정상 24개·위험 16개, 40/40 일치 |
| 개발 문제의 이름·주석·공백·Unicode 변형 | 40/40 일치 |
| 전체 회귀 | 2026-09-17, 17개 테스트 통과 |
| 자원 제한 실행 | 9/18 사용자 WSL 보고: CPU 2, RAM 3.8Gi, Swap 0, 개발40 처리 28.704초·판정 일치 |

개발 문제의 성적은 비공개셋 일반화 성능이 아닙니다. 자원 제한 실행은 깨끗한 오프라인 재현이나
모든 비공개 입력의 10분 내 처리를 보장하지 않습니다. 저장된 근거는 [실험 기록](docs/experiments/README.md)을 참고하세요.

## 분석 범위

상한 없는/우회 가능한 발행, 실제 증가량과 검사량의 불일치, 가변 상한, 승인 없는/승인을 재사용하는 전송,
관리자만 예외인 제한, 예치금 전액 회수, 예치금과 임의 delegatecall, 제한된 재진입 구조를 다룹니다.
일부 분기·내부 호출·같은 파일 상속을 지원하며, 확인하지 못한 핵심 경로는 보류합니다.

루프·재귀·assembly·unchecked·일반 외부 호출·import·복잡한 상속 생성자·일반 proxy 등은 미지원입니다.
경로 수 64, 방문 노드 예산 400, 호출 깊이 8의 제한이 있습니다.
위험을 찾지 못했다는 이유만으로 정상이라고 판정하지 않습니다.
대회 라벨의 경계를 일반적인 모든 스마트 컨트랙트의 안전성 정의로 확대하지 않습니다.

## 파일 안내

```text
scripts/             분석 진입점, 구조 관찰, Slither 비교 도구
src/track1/          CLI·worker·판정 집계·자체 분석 규칙
tests/               회귀 테스트와 평가 전용 변형/기대 정답
reference/           대회 원문·schema·공개 표본 (보존)
docs/                분석 설명, 다음 계획, 현재 진행 상태
  experiments/       실제 실험 JSON과 코드/문제 해시
  history/           이전 세션 기록
results/             로컬 실행 결과·로그 (Git 제외)
```

- [분석 원리와 쉬운 실습](docs/EXPANDED_RULES.md): 코드 흐름, 개선 과정, 지원 한계.
- [전체 구조 HTML 설명서](docs/project-flow-guide.html): 폴더·Python 호출 흐름·판정 규칙·심사 답변 연습.
- [다음 작업](docs/PLAN.md): 오프라인 패키징과 제출 준비.
- [현재 진행 기록](docs/PROGRESS.md): 실제 완료 사항, 사용자 실습, 남은 일.
- [대회 원문](reference/TRACK1_README.md) · [출력 스키마](reference/schema.json).

개발 시 코드 구조를 직접 보려면 `scripts/inspect_sol.py`, IR은 `scripts/inspect_ir.py`를 사용합니다.
이 도구들의 출력은 사람이 읽는 디버그용이며 채점 JSON이 아닙니다.

## 제출 전 남은 작업

1. 채점 OS/아키텍처, Docker 이미지 반입 가능 여부, 용량 제한·제출 경로 확인.
2. 런타임·컴파일러·의존성 버전 고정 및 오프라인 패키징.
3. 깨끗한 환경에서 네트워크 차단·2CPU/4GB·실패/시간 제한 통합 검증.
4. 파일별 근거 문구와 중복 근거 정리, 실행 안내·라이선스 고지·기여 내역·필수 제출물 완성.

Slither가 AST/CFG/SlithIR을 제공하고 자체 규칙이 대회 판정을 수행합니다.
기본 detector 경고를 악성 라벨로 일괄 변환하지 않습니다.
공개 표본의 MIT 고지를 보존하며 Slither는 AGPL-3.0입니다. 배포 의존성의 전체 고지는 패키징 단계에서 정리합니다.
구현·변형 생성·자동 실험에는 AI가 기여했고, 사용자는 WSL 설정과 CLI 자원 제한 실행을 직접 수행했습니다.
사용자의 모든 분석 규칙 이해가 확인된 상태는 아닙니다.
