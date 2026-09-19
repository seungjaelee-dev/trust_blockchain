# 제3자 소프트웨어 고지

이 프로젝트는 Solidity 컴파일러와 Slither의 분석 결과 위에 자체 판정·보고 계층을 구현합니다. 아래 도구를 직접 개발했다고 주장하지 않습니다. 공개 표본의 MIT 헤더와 각 의존성의 저작권·라이선스 고지를 보존합니다.

## 주요 구성 요소

| 구성 요소 | 고정 버전 | 출처 | 수집한 라이선스 정보 |
|---|---|---|---|
| Python | 3.12.3 | [CPython](https://github.com/python/cpython/tree/v3.12.3) | PSF 및 포함된 제3자 고지 |
| Slither | 0.11.6 | [Slither](https://github.com/crytic/slither/tree/0.11.6) | AGPL v3; 설치 패키지의 원문 수록 |
| crytic-compile | 0.4.2 | [crytic-compile](https://github.com/crytic/crytic-compile) | 설치 메타데이터: `AGPL-3.0-only` |
| solc-select | 1.2.0 | [solc-select](https://github.com/crytic/solc-select) | AGPL v3; 설치 패키지의 원문 수록 |
| Solidity compiler | 0.8.20 | [Solidity](https://github.com/ethereum/solidity/tree/v0.8.20) | `solc --license`의 GPL v3 및 포함 구성 요소 고지 |
| Python 기반 이미지 | `3.12.3-slim-bookworm` | [Docker Official Image 소스](https://github.com/docker-library/python) | Debian 패키지별 고지와 공통 라이선스 |

실행 시에는 포함된 `/usr/local/bin/solc`를 직접 사용합니다. `solc-select`로 컴파일러를 내려받지 않습니다.

## 포함된 원문과 재현 정보

- [Python 패키지 고지](third_party/PYTHON-LICENSES.txt): 실제 이미지에 설치된 라이선스·NOTICE·AUTHORS 파일. 파일별 구분선으로 출처를 표시했습니다.
- [컴파일러 고지](third_party/SOLC-LICENSE.txt): 제출용 바이너리의 `--license` 출력.
- [기반 이미지 고지](third_party/BASE-IMAGE-COPYRIGHT.txt): Python 라이선스, Debian의 copyright 및 공통 라이선스 파일.
- [OS 구성 목록](third_party/OS-PACKAGES.tsv): 설치 버전과 소스 패키지 이름·버전.
- [수집 명세](third_party/manifest.json): Python 패키지 54개의 버전·출처 메타데이터, 수집 이미지 ID, 고정 의존성 목록과 고지 파일의 SHA-256.

`crytic-compile 0.4.2` 설치본에는 별도 고지 파일이 발견되지 않았습니다. 해당 패키지의 라이선스 표현은 수집 명세에 보존했으며, AGPL v3 본문은 Python 고지의 Slither 라이선스 부분에도 들어 있습니다. 이를 crytic-compile에서 수집한 원문이라고 표시하지 않습니다.

고지는 저장소와 Docker 이미지의 `/opt/trust1/notices/`에 포함됩니다. 수집 방법은 [third_party/README.md](third_party/README.md)를 참고하세요.

## 수집 범위

이 자료는 설치본의 고지와 버전 목록입니다. 모든 의존성의 대응 소스 아카이브를 수집한 자료는 아닙니다. 위 링크는 upstream 출처이며 소스 아카이브 동봉을 대신했다고 주장하지 않습니다. 최종 이미지·바이너리 재배포 시에는 해당 라이선스 원문에 따라 필요한 소스 제공 방법도 함께 확인해야 합니다.

이 고지로 프로젝트 자체 코드에 새 라이선스를 부여하지 않습니다. 각 구성 요소의 기존 라이선스가 유지됩니다.
