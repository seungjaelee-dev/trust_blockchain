"""CLI로 개발 문제를 평가하고 실행 결과와 근거를 파일로 보존한다."""
import json
from pathlib import Path
import subprocess
import sys
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "tests/fixtures/variants/expanded"
expected = json.loads((DIRECTORY / "expected.json").read_text(encoding="utf-8"))
run = subprocess.run([sys.executable, str(ROOT / "scripts/analyze.py"), str(DIRECTORY)],
                     capture_output=True, text=True, timeout=540)
out = ROOT / "results"
out.mkdir(exist_ok=True)
label = sys.argv[1] if len(sys.argv) > 1 else "expanded"
(out / f"{label}.json").write_text(run.stdout, encoding="utf-8")
(out / f"{label}.log").write_text(run.stderr, encoding="utf-8")
if run.returncode:
    raise SystemExit(run.stderr)
items = json.loads(run.stdout)
Draft202012Validator(json.loads((ROOT / "reference/schema.json").read_text(encoding="utf-8"))).validate(items)
counts = {"correct": 0, "wrong": 0, "uncertain": 0}
for item in items:
    want = expected[item["file"]]["verdict"]
    got = item["verdict"]
    status = "correct" if got == want else "uncertain" if got == "UNCERTAIN" else "wrong"
    counts[status] += 1
    print(f'{status:9} {item["file"]:34} {want:10} {got}')
    if status != "correct":
        print("  " + " / ".join(item["reasons"])[-1600:])
print(counts)
