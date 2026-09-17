# 실험 기록

분석 패키지는 이 폴더의 정답/결과를 읽지 않습니다. 공개·개발 변형의 검증 근거이며 비공개 성능이 아닙니다.

| 파일 | 내용 |
| --- | --- |
| [expanded-baseline.json](expanded-baseline.json) | 확장 전 최초29개 개발 문제의 출력 |
| [expanded-results.json](expanded-results.json) | 9/17 확장 후 개발40개 판정·이유·근거 |
| [slither-baseline.json](slither-baseline.json) | 대표10개에 대한 기본 Slither detector 경고 |
| [experiment-snapshot.json](experiment-snapshot.json) | 9/17 검증 당시 코드/문제 SHA256과 실행 정보 |

snapshot은 당시 파일 경로의 역사적 기록입니다. 9/18 정리로 일회성 API 관찰 도구는 삭제되고
실험 JSON은 이 폴더로 이동했습니다. 이를 현재 전체 작업 트리와 동일한 고정본이라고 주장하지 않습니다.
당시 미지원 범위와 수정 이력은 [분석 설명](../EXPANDED_RULES.md)에 있습니다.

9/18 사용자 자원 제한 실행 원본은 로컬 `results/limited.json`·`limited.log`에 보존했습니다.
사용자 보고: CPU2, RAM3.8Gi, Swap0, real28.704초. 네트워크 차단 검증은 아직 아닙니다.

재실행:

```bash
python tests/evaluate_variants.py my-run
python scripts/compare_baseline.py
```

첫 명령은 results/에 새 결과를 저장하고, 두 번째는 이 폴더의 slither-baseline.json과
results/baseline/의 상세 결과를 갱신합니다.
