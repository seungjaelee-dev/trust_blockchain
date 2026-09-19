# 최종 제출 안내

기본 실행 명령과 출력 계약은 [README](../README.md), 개발·추가 검증은 [DOCKER](DOCKER.md), 구성 요소의 고지는 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)를 따릅니다.

## 1. 제출할 변경 확인

저장소 루트에서 확인합니다.

```bash
git status --short
git diff --check
git diff --stat
git diff --cached --stat
git ls-files '*.log'
```

소스, 테스트, 공개 원본, 문서, Docker 설정·고정 의존성, `artifacts/docker/solc-0.8.20`, `third_party/`는 보존합니다. 실행 로그, `results/`, 가상환경, 캐시, 이미지 tar는 Git 대상이 아닙니다. `docs/experiments/`의 선별된 검증 기록은 실험 근거로 보존합니다.

변경을 검토한 뒤 Git에 추가·커밋합니다. 커밋과 push는 사용자가 선택한 시점에 수행합니다. `.gitignore`만으로 이미 추적된 파일이 제외되지는 않으므로 추적 목록도 확인합니다.

## 2. 커밋과 최종 이미지 연결

깨끗한 clone에서 Linux/WSL 기준으로 실행합니다. 최초 빌드는 온라인 준비 단계입니다.

```bash
git rev-parse HEAD
docker build --platform linux/amd64 -t trust404-track1:submission .
docker image inspect trust404-track1:submission --format '{{.Id}}'
mkdir -p results
docker run --rm --network none --cpus 2 --memory 4g \
  --mount "type=bind,src=$(pwd)/reference/public,dst=/input,readonly" \
  trust404-track1:submission /input \
  > results/submission-public.json 2> results/submission-public.log
```

파일 5개가 모두 출력되는지, JSON 배열 외의 로그가 stdout에 섞이지 않는지, 공개 정답과 판정이 일치하는지 확인합니다. 개발 환경이 준비된 경우 `reference/schema.json`으로 JSON도 검증합니다. 판정 코드가 바뀌었다면 관련 회귀 테스트와 실패 사례 검증을 다시 실행합니다.

검증 결과에는 commit, 이미지 ID, 입력과 실행 조건을 함께 남깁니다. 기존 실험의 이미지 ID와 새 이미지 ID를 혼동하지 않습니다. 공개·자체 변형 샘플의 통과를 비공개 정확도로 설명하지 않습니다.

## 3. 오프라인 전달

주최 측이 이미지 파일 반입을 받는 경우에 사용합니다. 저장소 clone만으로 네트워크가 차단된 컴퓨터에서 최초 빌드까지 가능하다고 가정하지 않습니다.

```bash
docker save -o trust404-track1-submission.tar trust404-track1:submission
sha256sum trust404-track1-submission.tar
# 전달받은 컴퓨터
docker load -i trust404-track1-submission.tar
```

반입 파일의 SHA-256을 비교하고 README의 `--network none` 명령으로 실행합니다. 입력 폴더는 절대 경로로 연결합니다. 실제 전달 형식·용량·플랫폼은 주최 측 안내를 확인합니다.

고지 파일은 이미지에 포함되어 있습니다. 현재 고지 묶음은 대응 소스 아카이브 전체를 포함하지 않으므로, 바이너리·이미지 전달 방식에 따른 소스 제공도 각 의존성의 라이선스 원문에 맞춰 확인합니다.
