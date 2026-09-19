"""폴더 바로 아래 .sol 파일을 순차 처리하고 JSON 배열 하나를 출력한다."""

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def uncertain(path, reason):
    return {
        "file": path.name,
        "verdict": "UNCERTAIN",
        "reasons": [f"[분석 실행] {reason}"],
        "evidence": [],
    }


def stop_group(process):
    """WSL/Linux에서 worker와 같은 프로세스 그룹의 자식을 함께 종료한다."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def run_file(source, solc, timeout):
    worker = Path(__file__).with_name("worker.py")  ## 해당 코드로 이동
    with tempfile.TemporaryDirectory(
        prefix="trust1-"
    ) as temporary:  ## 운체위에 임시디렉만듦
        directory = Path(temporary)  ## 디렉토리 경로
        output = directory / "result.json"  ## 디렉토리/result.json 에다가 쓸 예정
        # 임시 작업 폴더로 컴파일 산출물을 원본 폴더와 분리한다.
        process = subprocess.Popen(
            [sys.executable, str(worker), str(source), str(solc), str(output)],
            cwd=directory,
            stdout=sys.stderr,
            stderr=sys.stderr,
            start_new_session=True,
        )
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return uncertain(
                source, "파일별 또는 남은 전체 시간 예산을 초과해 분석을 중단했습니다."
            )  ## 시간초와
        finally:
            stop_group(process)
        if process.returncode != 0 or not output.is_file():
            return uncertain(
                source, "분석 프로세스가 정상 결과 없이 종료되어 판단을 보류합니다."
            )
        return json.loads(
            output.read_text(encoding="utf-8")
        )  ## json 을 dictionary 로 변경


def positive_seconds(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("시간은 유한한 양수여야 합니다.")
    return number


def main():
    started = time.monotonic()  ##시간
    parser = argparse.ArgumentParser(description=__doc__)  ## --help
    parser.add_argument("input_dir", type=Path)  ## dir 경로 인자 1
    parser.add_argument(
        "--solc",
        type=Path,
        default=Path.home() / ".solc-select/artifacts/solc-0.8.20/solc-0.8.20",
        help="미리 설치한 실제 solc 바이너리 경로",
    )  ##추가 solc 인자 2
    parser.add_argument(
        "--file-timeout", type=positive_seconds, default=30
    )  ##파일 하나당 시간제한 3
    parser.add_argument(
        "--total-timeout", type=positive_seconds, default=540
    )  ## 전체 디렉토리 시간제한 4
    args = parser.parse_args()  ## 해당 인자들 실행
    # 실행 환경 검사
    if os.name != "posix":
        parser.error("이 CLI는 WSL/Linux Python에서 실행하세요.")
    if args.total_timeout > 540:
        parser.error("전체 시간 예산은 최대 540초입니다(출력/정리 여유 확보).")
    if not args.input_dir.is_dir():
        parser.error("존재하는 입력 디렉터리를 지정하세요.")
    try:
        files = sorted(
            (
                p.absolute()
                for p in args.input_dir.iterdir()
                if p.is_file() and p.suffix == ".sol"
            ),
            key=lambda p: p.name,
        )
    except OSError as error:
        parser.error(f"입력 목록을 읽을 수 없습니다: {error}")

    if not files:
        parser.error("입력 디렉터리 바로 아래에 .sol 파일이 없습니다.")
    results = [
        uncertain(p, "전체 시간 예산 소진으로 이 파일은 분석하지 못했습니다.")
        for p in files
    ]  ## 일단 uncertain(시간소진)으로 두기
    solc = args.solc.expanduser().resolve()
    if not solc.is_file() or not os.access(solc, os.X_OK):
        print(f"로컬 solc를 실행할 수 없습니다: {solc}", file=sys.stderr)
    deadline = started + args.total_timeout
    for index, source in enumerate(files):
        remaining = deadline - time.monotonic()
        if remaining <= 0:  ## 시간이 부족하다면 끝.
            break
        if not solc.is_file() or not os.access(
            solc, os.X_OK
        ):  ## 로컬에서 안된다면 해당 uncertain
            results[index] = uncertain(
                source,
                "지정한 로컬 solc 실행 파일을 사용할 수 없어 분석하지 못했습니다.",
            )
            continue
        print(f"[{index + 1}/{len(files)}] {source.name}", file=sys.stderr)
        try:
            results[index] = run_file(source, solc, min(args.file_timeout, remaining))
        except Exception as error:
            print(f"{source.name}: {type(error).__name__}: {error}", file=sys.stderr)
            results[index] = uncertain(
                source, f"분석 실행 오류({type(error).__name__})로 판단을 보류합니다."
            )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
