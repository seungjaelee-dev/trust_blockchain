# TRUST404 Track 1 — Smart Contract Threat Detection

**Solidity 소스코드의 권한·실행 흐름·자산 변경을 분석하고, 파일별 판정과 코드 위치를 JSON으로 출력하는 CLI입니다.**

Slither와 Solidity compiler(solc)가 제공하는 코드 구조에 자체 판정 규칙을 적용합니다. 파일명·주석의 정답 라벨을 판정에 사용하지 않으며, 분석 실행 중 외부 API·LLM·다운로드에 의존하지 않습니다.

## 빠른 실행 — Docker

호스트에는 **Git과 Docker**가 필요합니다. Python·Slither·solc는 이미지에 포함되므로 별도 Python 설치나 준비 스크립트 실행은 필요하지 않습니다.

아래 명령은 **Linux 또는 WSL의 Bash 터미널** 기준입니다. Windows에서는 Docker Desktop을 실행하고 사용하는 WSL 배포판의 통합을 활성화하세요. `docker version`에서 Client와 Server가 모두 표시되어야 합니다.

### 1. 저장소 받기와 빌드

```bash
git clone https://github.com/seungjaelee-dev/trust_blockchain.git
cd trust_blockchain
docker build --platform linux/amd64 -t trust404-track1:submission .
```

최초 빌드에는 기본 이미지와 Python 패키지를 받기 위한 인터넷이 필요합니다. 저장소에 포함된 `artifacts/docker/solc-0.8.20`은 SHA256 검증 후 `/usr/local/bin/solc`에 설치됩니다. **완성된 이미지의 분석 실행은 오프라인으로 가능합니다.**

### 2. 공개 표본 분석

저장소 최상위 폴더에서 실행합니다.

```bash
mkdir -p results
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/reference/public,target=/input,readonly" \
  trust404-track1:submission \
  > results/public.json 2> results/public.log
```

`results/public.json`에 판정 결과, `results/public.log`에 진행·진단 로그가 저장됩니다. 입력은 읽기 전용입니다. 추가 swap은 허용하지 않으며 CPU 2개·메모리 4GB를 상한으로 설정합니다.

### 3. 원하는 디렉터리 분석

`INPUT_DIR`을 `.sol` 파일이 들어 있는 **실제 절대 경로**로 바꾸세요.

```bash
INPUT_DIR="/absolute/path/to/cases"
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=${INPUT_DIR},target=/input,readonly" \
  trust404-track1:submission \
  > results/analysis.json 2> results/analysis.log
```

컨테이너는 기본으로 `/input`을 분석합니다. 입력 디렉터리 **바로 아래의 `.sol` 파일 전체**를 이름순으로 처리하며 하위 폴더는 재귀 탐색하지 않습니다. 소스 변경 후에는 이미지를 다시 빌드해야 변경 사항이 반영됩니다.

## 오프라인 환경으로 이미지 전달

인터넷이 없는 컴퓨터에서는 최초 빌드에 필요한 파일을 내려받을 수 없습니다. 이미지 반입 방식으로 제출할 경우 준비 환경에서 빌드한 이미지를 저장해 전달합니다. 실제 제출 형식·용량·CPU 아키텍처는 주최 측 안내를 따릅니다.

빌드한 컴퓨터에서:

```bash
mkdir -p artifacts
docker save -o artifacts/trust404-track1.tar trust404-track1:submission
(cd artifacts && sha256sum trust404-track1.tar > trust404-track1.tar.sha256)
```

두 파일을 전달한 뒤, 오프라인 컴퓨터의 해당 폴더에서:

```bash
sha256sum -c trust404-track1.tar.sha256
docker load -i trust404-track1.tar
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=/absolute/path/to/cases,target=/input,readonly" \
  trust404-track1:submission
```

마지막 명령은 JSON을 stdout으로 출력합니다. 필요하면 `> analysis.json 2> analysis.log`를 붙여 저장하세요. 이미지에는 코드와 런타임이 포함되어 있으므로 입력 폴더만 연결하면 됩니다.

## 입출력 계약

| 항목 | 동작 |
| --- | --- |
| 입력 | 디렉터리 바로 아래의 `.sol` 파일 |
| stdout | 파일마다 객체 하나를 담은 JSON 배열 하나 |
| stderr | 진행 상황·컴파일 경고·진단 로그 |
| 필수 필드 | `file`, `verdict`, `reasons`, `evidence` |
| 근거 위치 | 원본 입력의 함수와 1부터 시작하는 줄 번호 |
| 개별 컴파일·분석 실패 | 해당 파일을 `UNCERTAIN`으로 기록하고 계속 처리 |
| 시간 초과 | 해당 파일 또는 미처리 파일을 이유와 함께 `UNCERTAIN`으로 기록 |
| 종료 코드 | 일괄 처리 완료는 `0`; 없는 폴더·빈 폴더·잘못된 인자는 `2` |

출력 형식 예시입니다. 파일명·함수·줄 번호는 설명용입니다.

```json
[
  {
    "file": "example.sol",
    "verdict": "MALICIOUS",
    "reasons": [
      "사용자 ETH가 예치되지만 소유자는 사용자별 예치 권리와 무관하게 금고 전체 ETH를 회수할 수 있습니다."
    ],
    "evidence": [
      { "function": "deposit()", "line": 7 },
      { "function": "sweep()", "line": 14 }
    ]
  }
]
```

정확한 계약은 [대회 원문](reference/TRACK1_README.md)과 [JSON Schema](reference/schema.json)를 따릅니다. `MALICIOUS`에는 비어 있지 않은 위치 근거를 제공합니다. 여러 위험 규칙이 성립하면 해당 위험들의 이유와 근거를 함께 수집합니다.

### 시간 제한

파일별 기본 제한은 **30초**, 전체 분석 예산은 **540초**입니다. worker 프로세스를 파일별로 격리하며 timeout 시 같은 프로세스 그룹의 자식도 종료합니다. 시작할 때 전체 파일의 기본 결과를 마련해 예산이 소진되어도 미처리 파일을 JSON에 포함합니다.

다음처럼 이미지 이름 뒤에 입력 경로와 옵션을 전달합니다. 전체 예산은 최대 540초입니다.

```bash
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/reference/public,target=/input,readonly" \
  trust404-track1:submission /input --file-timeout 30 --total-timeout 540
```

## 분석 방법과 판정 의미

```text
입력 디렉터리
  → cli.py: 파일 목록 수집·시간 예산 관리
  → worker.py: 파일별 solc 컴파일·Slither 구조 분석
  → verdict.py: 자체 규칙 호출·컨트랙트별 결과 집계
  → rules/: 권한 → 조건 → 상태 변경 → 사용자 영향 확인
  → cli.py: 파일별 결과를 JSON 배열로 출력
```

Slither는 AST, 제어 흐름(CFG), 중간 표현(SlithIR)을 제공합니다. 자체 규칙은 이 정보로 **누가 호출할 수 있는지, 검사가 우회되는지, 검사한 값과 실제 바뀌는 값이 같은지**를 연결합니다. Slither 기본 detector의 경고를 모두 악성으로 변환하지 않습니다.

| 판정 | 의미 |
| --- | --- |
| `MALICIOUS` | 지원 범위에서 경고·차단 대상 경로의 충분한 증거를 확인 |
| `BENIGN` | 지원하는 패턴의 안전 조건을 확인하고 파일 단위 집계 조건을 충족 |
| `UNCERTAIN` | 미지원 구조·불충분한 근거·컴파일 실패·시간 제한으로 판단 보류 |

`MALICIOUS`는 개발자의 의도를 단정하지 않습니다. `BENIGN`도 모든 공격에 대한 안전 보증은 아닙니다. 대회 기준상 코드가 강제하는 공급량 상한 내의 발행이나 소유자에게도 동일하게 적용되는 정지 기능은 그 자체만으로 악성이 아닙니다.

### 주요 분석 패턴

| 대상 | 확인하는 관계 |
| --- | --- |
| 공급량 발행 | 실제 증가 후 공급량의 고정 상한, 우회 분기·추가 발행·상한 변경 가능성 |
| 토큰 대리 전송 | 타인 잔액 이동과 당사자 확인 또는 승인 한도 검사·차감의 연결 |
| 비대칭 전송 제한 | 관리자가 제한을 변경하면서 자신만 우회할 수 있는지 |
| 금고 자산 회수 | 사용자 예치 경로와 관리자의 전체 자산 인출 권한 |
| 임의 `delegatecall` | 예치 자산과 관리자 제어 대상·데이터의 연결 |
| 제한된 재진입 패턴 | 외부 지급·장부 갱신 순서와 잠금·차감 방식 |

일부 분기·내부 함수 호출·같은 파일의 상속을 분석합니다. 경로 해석에는 경로 수 64, 방문 노드 예산 400, 호출 깊이 8의 제한이 있습니다.

루프·재귀·assembly·unchecked·일반 외부 호출·import·복잡한 상속 생성자·일반 proxy는 지원이 제한되거나 미지원입니다. 포함된 solc는 **0.8.20 한 버전**이며, 호환되지 않는 pragma를 위해 실행 중 다른 컴파일러를 설치하지 않습니다. 모든 Solidity 프로그램을 완전하게 판정하는 도구는 아닙니다.

## 실행 환경

| 구성 | 버전·설정 |
| --- | --- |
| 이미지 대상 | Linux amd64 |
| 기본 이미지 | `python:3.12.3-slim-bookworm` |
| Python | 3.12.3 |
| Slither | 0.11.6 |
| crytic-compile | 0.4.2 |
| solc | 0.8.20, `/usr/local/bin/solc` |
| Python 패키지 목록 | [docker/requirements.lock](docker/requirements.lock) |
| 실행 사용자 | UID/GID `10001:10001`, 쓰기 가능한 `HOME=/home/trust1` |

Python 패키지는 버전으로 고정하며 solc 바이너리는 SHA256으로 검증합니다. 기본 이미지 digest와 Python 배포 파일 해시까지 고정한 빌드는 아니므로, 최종 검증한 이미지 자체는 `docker save`와 해시 기록으로 보존할 수 있습니다.

## 검증 기록

수행 시점과 환경을 구분한 기록입니다. 이번 README 갱신에서 분석 테스트를 다시 실행한 것은 아닙니다.

| 항목 | 결과·근거 |
| --- | --- |
| 공개 표본 | 5/5 기대 판정 일치: P1·P4 `BENIGN`, P2·P3·P5 `MALICIOUS` |
| 자체 개발 변형셋 | 정상 24개·위험 16개, 40/40 일치 |
| 의미 보존 변형 | 이름·주석·공백·Unicode 변형 40/40 일치 |
| 개발 환경 회귀 | 2026-09-17, schema·실패 격리·timeout 등을 포함한 17개 테스트 통과 |
| WSL 자원 제한 | 9/18 사용자 실행: CPU 2, RAM 3.8Gi, Swap 0, 개발 40개 처리 28.704초 |
| Docker 공개 표본 | 9/19, 네트워크 차단·2CPU/4GB에서 공개 5개 기대 판정 일치, HOME 권한 오류 없음 |
| 별도 clone 재현 | 9/19 사용자 보고: 다른 디렉터리에서 clone·Docker build·run 정상 동작 |

자체 변형셋은 규칙 개발에 사용한 데이터로, 독립 비공개셋의 일반화 성능을 나타내지 않습니다. 최종 Docker 환경에서 정상·오류 입력을 섞는 추가 검증은 별도로 남아 있습니다. 상세 결과는 [실험 기록](docs/experiments/README.md)에 있습니다.

개발 변형셋을 Docker로 분석하려면:

```bash
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/tests/fixtures/variants/expanded,target=/input,readonly" \
  trust404-track1:submission \
  > results/expanded.json 2> results/expanded.log
```

## 저장소 안내

```text
Dockerfile                   제출용 실행 이미지
docker/requirements.lock     Python 의존성 버전
artifacts/docker/solc-0.8.20  빌드에 포함할 Linux 컴파일러
scripts/analyze.py           CLI 진입점
src/track1/
  cli.py                     디렉터리 처리·시간 제한·JSON 출력
  worker.py                  파일별 컴파일·분석 실행
  verdict.py                 규칙 호출·파일 단위 판정 집계
  rules/                     자체 규칙과 경로 해석 보조 코드
tests/                       회귀 테스트·변형 입력·평가용 정답
reference/                   대회 원문·출력 스키마·공개 표본
docs/                        구조 설명·분석 원리·실험 기록
results/                     로컬 결과·로그 (Git 제외)
```

공개 라벨과 기대 정답은 평가 자료입니다. Docker 분석 이미지에는 분석 코드와 런타임을 포함하며, 테스트 정답 목록을 판정에 사용하지 않습니다.

- [전체 구조 HTML 설명서](docs/project-flow-guide.html): 내려받아 브라우저로 열면 폴더·Python 호출·규칙 흐름을 탐색할 수 있습니다.
- [분석 원리와 실습](docs/EXPANDED_RULES.md): 정상·위험 쌍과 지원 한계.
- [Docker 상세 안내](docs/DOCKER.md): 개발 시 소스 연결과 이미지 전달.
- [실험 기록](docs/experiments/README.md): 실제 결과와 비교 자료.
- [진행 기록](docs/PROGRESS.md) · [남은 계획](docs/PLAN.md).

## 기반 도구와 기여

Slither/solc의 구조 분석과 프로젝트 자체 판정 계층을 구분합니다. 자체 구현 범위는 디렉터리 CLI, 실패·시간 제한 처리, 규칙과 판정 집계, 근거 JSON, 변형 테스트 및 설명 자료입니다. 구현·변형 생성·자동 실험에는 AI가 기여했으며, 사용자는 WSL 설정·자원 제한 실행·별도 clone의 Docker 재현을 수행했습니다.

공개 표본의 MIT 고지를 보존합니다. Slither는 AGPL-3.0이며 기반 도구·패키지는 각각의 라이선스를 따릅니다. 최종 이미지 배포에 필요한 의존성 전체 고지와 소스 제공 정리는 별도 제출 점검 항목입니다.
