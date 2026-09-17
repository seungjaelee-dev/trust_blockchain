"""저장소에서 설치 없이 사용하는 폴더 분석 진입점."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from track1.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
