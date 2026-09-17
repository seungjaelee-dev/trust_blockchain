"""기본 Slither detector 경고와 자체 verdict를 비교. 경고를 라벨로 변환하지 않는다."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOLC = Path.home() / ".solc-select/artifacts/solc-0.8.20/solc-0.8.20"
OUT = ROOT / "results/baseline"
OUT.mkdir(parents=True, exist_ok=True)
cases = list(sorted((ROOT / "reference/public").glob("*.sol")))
cases += [ROOT / "tests/fixtures/variants/expanded" / name for name in
          ("cap_branch_risk.sol", "allowance_risk.sol", "reentry_risk.sol", "reentry_locked_safe.sol", "withdraw_risk.sol")]
summary = []
for source in cases:
    output = OUT / (source.stem + ".json")
    # Slither refuses overwriting its JSON report. Use a new temporary directory
    # for every run, then copy the finished JSON to our reproducible result path.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        report = Path(temp) / "report.json"
        run = subprocess.run([str(Path(sys.executable).with_name("slither")), str(source),
                              "--solc", str(SOLC), "--json", str(report)],
                             capture_output=True, text=True, timeout=40)
        if not report.exists():
            raise RuntimeError(run.stderr)
        data = json.loads(report.read_text())
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    detectors = data.get("results", {}).get("detectors", [])
    checks = sorted({d["check"] for d in detectors})
    summary.append({"file": str(source.relative_to(ROOT)), "success": data["success"],
                    "detectors": checks, "finding_count": len(detectors)})
    print(source.name, checks, flush=True)
    if not data["success"]:
        raise RuntimeError(data.get("error"))
summary_path = ROOT / "docs/experiments/slither-baseline.json"
summary_path.parent.mkdir(parents=True, exist_ok=True)
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
