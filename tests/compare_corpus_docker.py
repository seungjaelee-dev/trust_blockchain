"""Paired offline evaluation; only Solidity inputs are mounted into analyzers."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import time

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score(items, gold):
    counts = Counter(correct=0, wrong=0, uncertain=0)
    matrix, categories = defaultdict(Counter), defaultdict(Counter)
    for item in items:
        truth = gold[item["file"]]
        guess = item["verdict"]
        outcome = "uncertain" if guess == "UNCERTAIN" else "correct" if guess == truth["verdict"] else "wrong"
        counts[outcome] += 1
        matrix[truth["verdict"]][guess] += 1
        categories[truth["category"]][outcome] += 1
        categories[truth["category"]]["total"] += 1
    decided = counts["correct"] + counts["wrong"]
    return {"total": len(items), **counts, "coverage": decided / len(items),
            "decided_accuracy": counts["correct"] / decided if decided else None,
            "net_score": max(0, counts["correct"] - counts["wrong"]),
            "false_positives": matrix["BENIGN"]["MALICIOUS"],
            "false_negatives": matrix["MALICIOUS"]["BENIGN"],
            "decisions_on_uncertain_gold": matrix["UNCERTAIN"]["BENIGN"] + matrix["UNCERTAIN"]["MALICIOUS"],
            "confusion_matrix": dict(matrix), "by_category": dict(categories)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--before", default="trust404-track1:reporting-review")
    parser.add_argument("--after", default="trust404-track1:flow-review")
    parser.add_argument("--output", default="stage1-corpus-comparison")
    args = parser.parse_args()
    corpus = args.corpus.resolve()
    output = ROOT / "results" / args.output
    output.mkdir(parents=True, exist_ok=True)
    gold = {x["file"]: x for x in json.loads((corpus / "answers/answers.json").read_text(encoding="utf-8"))}
    sources = sorted((corpus / "cases").glob("*.sol"))
    assert len(sources) == 300 and {p.name for p in sources} == set(gold)
    manifest = {}
    for line in (corpus / "manifest_sha256.txt").read_text().splitlines():
        checksum, name = line.split(maxsplit=1)
        manifest[name.strip()] = checksum
    for source in sources + [corpus / "answers/answers.json"]:
        assert digest(source) == manifest[source.relative_to(corpus).as_posix()], source
    validator = Draft202012Validator(json.loads((ROOT / "reference/schema.json").read_text(encoding="utf-8")))
    report = {"date_utc": datetime.now(timezone.utc).isoformat(), "corpus": str(corpus),
              "dataset_note": "Synthetic corpus; some families were used during rule development. Original labels preserved.",
              "batch_size": 10, "batch_count": 30, "network": "none", "cpus": 2, "memory": "4g",
              "additional_swap": False, "file_timeout": 60, "total_timeout_per_batch": 540,
              "execution_order": "sequential paired batches, alternates before/after order",
              "input_sha256": {p.name: digest(p) for p in sources},
              "answers_sha256": digest(corpus / "answers/answers.json"), "images": {}, "batches": []}
    hash_code = ("import hashlib,json,pathlib; r=pathlib.Path('/app'); "
                 "print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() "
                 "for p in sorted((r/'src').rglob('*.py'))}))")
    for label, tag in [("before", args.before), ("after", args.after)]:
        info = json.loads(subprocess.check_output(["docker", "image", "inspect", tag], text=True))[0]
        code_hashes = json.loads(subprocess.check_output(["docker", "run", "--rm", "--network", "none",
                                "--entrypoint", "python", info["Id"], "-c", hash_code], text=True))
        report["images"][label] = {"tag": tag, "id": info["Id"], "source_sha256": code_hashes}
    mismatches = [n for n, h in report["images"]["after"]["source_sha256"].items() if digest(ROOT / n) != h]
    assert not mismatches, f"Current image does not match source: {mismatches}"
    results = {"before": [], "after": []}
    print("Validated 300 source hashes; image IDs pinned; running 30 paired batches.", flush=True)
    for start in range(0, len(sources), 10):
        number = start // 10 + 1
        batch = output / "inputs" / f"{number:02}"
        batch.mkdir(parents=True, exist_ok=True)
        paths = sources[start:start + 10]
        for path in paths:
            shutil.copyfile(path, batch / path.name)
        assert {p.name for p in batch.iterdir()} == {p.name for p in paths}
        order = ["before", "after"] if number % 2 else ["after", "before"]
        for label in order:
            command = ["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "4g",
                       "--memory-swap", "4g", "--mount", f"type=bind,source={batch},target=/input,readonly",
                       report["images"][label]["id"], "/input", "--file-timeout", "60", "--total-timeout", "540"]
            began = time.monotonic()
            run = subprocess.run(command, capture_output=True, text=True, timeout=590)
            elapsed = round(time.monotonic() - began, 3)
            (output / f"{label}-{number:02}.json").write_text(run.stdout, encoding="utf-8")
            (output / f"{label}-{number:02}.log").write_text(run.stderr, encoding="utf-8")
            assert run.returncode == 0, run.stderr
            items = json.loads(run.stdout)
            validator.validate(items)
            assert len(items) == 10 and {x["file"] for x in items} == {p.name for p in paths}
            for item in items:
                for ref in item["evidence"]:
                    if "line" in ref:
                        assert 1 <= ref["line"] <= len((batch / item["file"]).read_text().splitlines()), item
            results[label].extend(items)
            report["batches"].append({"batch": number, "version": label, "elapsed_seconds": elapsed,
                                       "verdict_counts": dict(Counter(x["verdict"] for x in items))})
            print(f"batch {number:02}/30 {label}: {elapsed:.2f}s, {Counter(x['verdict'] for x in items)}", flush=True)
        save(output / "checkpoint.json", report)
    report["scores"], report["runtime"] = {}, {}
    for label, items in results.items():
        items.sort(key=lambda x: x["file"])
        save(output / f"{label}.json", items)
        report["scores"][label] = score(items, gold)
        # Cross-check our metric implementation against the corpus's evaluator.
        reference = json.loads(subprocess.check_output(["python3", str(corpus / "evaluate.py"), str(output / f"{label}.json")], text=True))
        for key in ["correct", "wrong", "uncertain", "coverage", "decided_accuracy", "net_score"]:
            assert report["scores"][label][key] == reference[key], (key, label)
        times = [x["elapsed_seconds"] for x in report["batches"] if x["version"] == label]
        reasons = [r for x in items for r in x["reasons"]]
        report["runtime"][label] = {"total_seconds": round(sum(times), 3), "median_batch_seconds": statistics.median(times),
                                    "max_batch_seconds": max(times),
                                    "timeout_items": sum(any("시간 예산" in r for r in x["reasons"]) for x in items),
                                    "compilation_failure_items": sum(any("구조 분석 실패" in r for r in x["reasons"]) for x in items)}
    before = {x["file"]: x for x in results["before"]}
    after = {x["file"]: x for x in results["after"]}
    fields = ["file", "category", "gold", "before", "after", "changed"]
    rows = [{"file": name, "category": gold[name]["category"], "gold": gold[name]["verdict"],
             "before": before[name]["verdict"], "after": after[name]["verdict"],
             "changed": before[name]["verdict"] != after[name]["verdict"]} for name in sorted(gold)]
    with (output / "comparison.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report["changes"] = [row for row in rows if row["changed"]]
    report["mismatches"] = {label: [x["file"] for x in items if x["verdict"] != "UNCERTAIN" and x["verdict"] != gold[x["file"]]["verdict"]]
                             for label, items in results.items()}
    report["schema_and_line_ranges"] = "passed for all 600 outputs"
    report["after_image_working_tree_differences_at_end"] = [n for n, h in report["images"]["after"]["source_sha256"].items() if digest(ROOT / n) != h]
    report["evaluation_script_sha256"] = digest(Path(__file__))
    save(output / "summary.json", report)
    save(ROOT / "docs/experiments" / f"{args.output}.json", report)
    print(json.dumps({"scores": report["scores"], "runtime": report["runtime"], "changed": len(report["changes"]),
                      "mismatches": report["mismatches"]}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
