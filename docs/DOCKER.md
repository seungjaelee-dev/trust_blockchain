# Docker 실행 환경

## 현재 상태

2026-09-19 기준 Docker 빌드와 네트워크 차단·2CPU/4GB 공개 표본 실행을 확인했습니다.
사용자도 별도 디렉터리에서 clone·build·run의 정상 동작을 보고했습니다.
제출용 기본 실행은 [README](../README.md)를 따르세요. 문서·고지 정리 후 현재 코드의 정상·위험·문법 오류 혼합60개를
오프라인 2CPU/4GB에서 검증했습니다. 상세 결과는 [제출 검증](experiments/submission-check.json)에 있습니다.

기존 WSL에서 정상 동작한 Python 3.12.3, Slither 0.11.6, crytic-compile 0.4.2,
solc 0.8.20과 설치 패키지 전체 버전을 고정합니다. Python 버전이 대회 필수 버전이라는
근거는 현재 제공된 원문에 없습니다. solc 0.8.20도 공개 표본 확인 버전입니다.
대상은 Linux amd64입니다. 채점 CPU 아키텍처와 이미지 반입 방식/용량은 추가 확인이 필요합니다.

`docker/requirements.lock`은 실제 WSL 설치 목록을 고정한 파일이며 테스트용 jsonschema도 포함합니다.
Python 기본 이미지는 정확한 버전 태그를 사용하되 아직 digest 고정은 하지 않았습니다.
패키지 배포 파일의 해시까지 고정한 lock은 아닙니다. 최초 빌드에는 인터넷이 필요합니다.
최종 이미지 tar와 SHA256을 보관하면 채점 실행에는 다운로드가 필요 없습니다.

## 1. Docker 설치 후 WSL 연결

Windows에 Docker Desktop을 설치·실행하고 Linux containers/WSL 2 backend를 사용합니다.
Settings → Resources → WSL Integration에서 Ubuntu-24.04를 활성화합니다.
WSL 터미널에서 `docker version`의 Client와 Server가 모두 보여야 합니다.

아래 명령은 모두 프로젝트 최상위 폴더의 WSL 터미널에서 실행합니다.

## 2. 환경과 현재 소스를 이미지로 만들기

```bash
docker build --platform linux/amd64 -t trust404-track1:dev .
```

Linux solc 바이너리는 `artifacts/docker/solc-0.8.20`에 Git으로 포함되어 있습니다.
새 clone에서도 Python이나 준비 스크립트 없이 build하면 됩니다. Dockerfile이 바이너리의
SHA256을 검증합니다. 실행 사용자의 HOME은 쓰기 가능한 `/home/trust1`입니다.

Dockerfile은 환경을 먼저 설치하고 소스를 마지막에 복사합니다.
코드만 바꿔 다시 build하면 기존 환경 설치 단계를 캐시로 재사용할 수 있습니다.

## 3. 오프라인·2CPU·4GB 실행

```bash
mkdir -p results
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/reference/public,target=/input,readonly" \
  trust404-track1:dev > results/docker-public.json 2> results/docker-public.log

docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/tests/fixtures/variants/expanded,target=/input,readonly" \
  trust404-track1:dev > results/docker-expanded.json 2> results/docker-expanded.log
```

stdout은 JSON 배열만, stderr는 로그입니다. 입력은 읽기 전용입니다.
CLI의 파일별 기본 60초/전체 540초 예산이 적용됩니다. 남은 전체 예산이 우선하므로 10개 입력에 각각 60초를 보장하지는 않습니다.
`--memory-swap 4g`를 메모리와 같게 지정해 추가 swap을 허용하지 않습니다.
WSL 호스트 메모리도 충분해야 하며 4GB는 예약량이 아닌 컨테이너 상한입니다.

## 4. 소스를 수정하면서 실행하기

```bash
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/src,target=/app/src,readonly" \
  --mount "type=bind,source=$(pwd)/scripts,target=/app/scripts,readonly" \
  --mount "type=bind,source=$(pwd)/reference/public,target=/input,readonly" \
  trust404-track1:dev
```

이 명령은 내 컴퓨터의 최신 src/scripts를 컨테이너에 연결합니다.
Python·Slither·solc는 이미지에 고정되어 있고 내 Python 코드만 바뀝니다.
패키지를 추가하거나 버전을 바꿀 때는 lock 검토와 재빌드가 필요합니다.

## 5. 제출용 최종본 저장과 복원

최종 소스를 반영해 다시 빌드하고, **소스를 연결하지 않은 3번 방식**으로 검증합니다.

```bash
docker build --platform linux/amd64 -t trust404-track1:submission .
mkdir -p artifacts
docker image inspect trust404-track1:submission > artifacts/submission-image.json
docker save -o artifacts/trust404-track1.tar trust404-track1:submission
(cd artifacts && sha256sum trust404-track1.tar > trust404-track1.tar.sha256)
```

인터넷이 없는 채점 컴퓨터에서는 전달받은 파일로 실행합니다.

```bash
sha256sum -c trust404-track1.tar.sha256
docker load -i trust404-track1.tar
docker run --rm --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=/absolute/path/to/cases,target=/input,readonly" \
  trust404-track1:submission
```

Dockerfile만 전달하면 오프라인에서 최초 build가 되지 않습니다. 완성된 이미지 전달이 필요합니다.
실제 설치 구성의 고지는 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)에 정리했습니다.
고지 파일도 이미지에 포함됩니다. 최종 commit과 이미지/tar 해시를 연결하는 절차는 [SUBMISSION](SUBMISSION.md)을 따르세요.

## 6. 개발용 전체 회귀 테스트

일반 분석에는 위의 `docker run`만 필요합니다. 아래는 저장소의 테스트까지 실행하려는 개발자용 명령입니다. Linux/WSL의 저장소 루트에서 실행합니다.

```bash
docker run --rm -i --network none --cpus 2 --memory 4g --memory-swap 4g \
  --mount "type=bind,source=$(pwd)/tests,target=/app/tests,readonly" \
  --mount "type=bind,source=$(pwd)/reference,target=/app/reference,readonly" \
  --env HOME=/tmp/trust1-test --entrypoint python \
  trust404-track1:submission - <<'PY'
from pathlib import Path
import runpy
import sys

compiler = Path.home() / ".solc-select/artifacts/solc-0.8.20/solc-0.8.20"
compiler.parent.mkdir(parents=True, exist_ok=True)
compiler.symlink_to("/usr/local/bin/solc")
sys.argv = ["unittest", "discover", "-s", "tests", "-v"]
runpy.run_module("unittest", run_name="__main__")
PY
```

테스트는 Python CLI를 직접 호출하므로 Docker 기본 진입점의 `--solc /usr/local/bin/solc`가 자동 전달되지 않습니다. 임시 HOME에 개발용 기본 경로를 만들고 포함된 바이너리로 연결합니다. 다운로드나 별도 컴파일러 설치는 없습니다. 컨테이너 종료 시 이 테스트용 경로도 사라집니다.
위 혼합 검증은 완료했으며, 최종 전달본을 새로 만들거나 코드를 바꾸면 해당 고정본을 확인해야 합니다.

공식 참고: [이미지 저장](https://docs.docker.com/reference/cli/docker/image/save/),
[네트워크 차단](https://docs.docker.com/engine/network/drivers/none/),
[소스 연결](https://docs.docker.com/engine/storage/bind-mounts/).
