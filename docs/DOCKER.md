# Docker 실행 환경

## 현재 상태

Docker 사용은 사용자에게 허용 확인을 받았습니다. 현재 PC에는 Docker가 없어 이미지 빌드와
컨테이너 시험은 아직 하지 못했습니다. 아래 파일은 준비된 빌드 설정이며 검증 완료 이미지가 아닙니다.

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
source ~/.venvs/trust1/bin/activate
python scripts/prepare_docker.py
docker build --platform linux/amd64 -t trust404-track1:dev .
```

준비 스크립트는 기존 solc를 복사하고 SHA256을 확인합니다. solc를 새로 설치하거나
버전을 바꾸지 않습니다. 복사본은 Git에서 제외한 artifacts/docker에 있습니다.
다른 PC에서 빌드하려면 동일한 Linux solc 파일을 `--solc /path/to/solc`로 지정합니다.

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
기존 CLI의 파일별 30초/전체 540초 예산이 그대로 적용됩니다.
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
sha256sum artifacts/trust404-track1.tar > artifacts/trust404-track1.tar.sha256
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
실제 제출 방식에 맞춘 라이선스 고지/소스 제공 정리와 최종 통합 검증은 아직 남아 있습니다.

공식 참고: [이미지 저장](https://docs.docker.com/reference/cli/docker/image/save/),
[네트워크 차단](https://docs.docker.com/engine/network/drivers/none/),
[소스 연결](https://docs.docker.com/engine/storage/bind-mounts/).
