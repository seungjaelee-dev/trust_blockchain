# 의존성 고지 자료

이 폴더는 실제 Docker 설치본에서 가져온 고지·구성 목록입니다. 전체 안내는 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)에 있습니다.

`manifest.json`의 `image_id`는 **수집에 사용한 이미지**입니다. 고지 파일을 추가한 최종 이미지와 ID가 달라도 의존성이 동일할 수 있습니다. 최종 이미지의 패키지 목록과 고정 버전은 별도로 검증합니다.

Linux/WSL에서 로컬 이미지로 다시 수집할 수 있습니다.

```bash
python scripts/collect_notices.py --image trust404-track1:submission
```

수집 스크립트는 이미지 ID를 먼저 확정하고 `--network none` 컨테이너로 설치 메타데이터와 고지를 읽습니다. `docker/requirements.lock`과 설치 버전이 다르면 실패합니다. 변경된 고지를 이미지에도 반영하려면 다시 빌드해야 합니다.

고지 텍스트의 원문은 수동 요약으로 덮어쓰지 않습니다. `OS-PACKAGES.tsv`는 이름·설치 버전·소스 패키지·소스 버전 순서이며, 대응 소스 자체는 포함하지 않습니다.
