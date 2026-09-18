"""Copy the verified local Linux solc into the Docker build context (no download)."""

import argparse
import hashlib
from pathlib import Path
import shutil

SOLC_SHA256 = "0479d44fdf9c501c25337fdc540419f1593b884a87b47f023da4f1c700fda782"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solc", type=Path, default=Path.home() /
                        ".solc-select/artifacts/solc-0.8.20/solc-0.8.20")
    args = parser.parse_args()
    source = args.solc.expanduser().resolve()
    if not source.is_file():
        parser.error(f"Local solc not found: {source}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOLC_SHA256:
        parser.error("solc SHA256 mismatch: expected the verified Linux amd64 0.8.20 binary")
    target = Path(__file__).resolve().parents[1] / "artifacts/docker/solc-0.8.20"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o755)
    print(f"Prepared {target}; SHA256 verified.")


if __name__ == "__main__":
    main()
