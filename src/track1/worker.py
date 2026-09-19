"""격리 프로세스에서 소스 하나를 읽는다. 결과는 전용 파일로 전달한다."""

import json
import os
from pathlib import Path
import sys


def analyze_file(source, solc):
    from slither.slither import Slither
    from track1.verdict import analyze

    analysis = Slither(str(source), solc=str(solc))
    return {"file": source.name, **analyze(analysis, source)}


def main():
    source, solc, output = map(Path, sys.argv[1:])
    # Python print뿐 아니라 라이브러리/자식 프로세스 stdout도 진단 스트림으로 보낸다.
    os.dup2(2, 1)
    try:
        result = analyze_file(source, solc)
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        result = {
            "file": source.name,
            "verdict": "UNCERTAIN",
            "reasons": [f"[컴파일·구조 분석] 컴파일 또는 구조 분석 실패({type(error).__name__}). "
                        "분석 구조를 확보하지 못해 판단을 보류합니다. 상세 진단은 stderr에 있습니다."],
            "evidence": [],
        }
    output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    # worker는 별도 Python 프로세스에서 파일 경로로 실행된다.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
