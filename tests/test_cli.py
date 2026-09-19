"""WSL 전용 통합 테스트: 실제 solc/Slither와 원본 JSON Schema 사용."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
import importlib.util
import io
from unittest.mock import patch

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/analyze.py"
SCHEMA = json.loads((ROOT / "reference/schema.json").read_text(encoding="utf-8"))


class CliTests(unittest.TestCase):
    def test_default_file_budget_and_remaining_total(self):
        spec = importlib.util.spec_from_file_location("budget_cli", ROOT / "src/track1/cli.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ["a.sol", "b.sol", "c.sol"]:
                (directory / name).write_text("pragma solidity ^0.8.20;")
            captured = io.StringIO()
            with patch.object(sys, "argv", [str(CLI), str(directory), "--solc", sys.executable]), \
                    patch.object(cli.time, "monotonic", side_effect=[1000, 1000, 1050, 1530]), \
                    patch.object(cli, "run_file", side_effect=lambda source, solc, seconds: cli.uncertain(source, "budget test")) as run_file, \
                    redirect_stdout(captured):
                self.assertEqual(cli.main(), 0)
            self.assertEqual([call.args[2] for call in run_file.call_args_list], [60, 60, 10])
            self.assertEqual([x["file"] for x in json.loads(captured.getvalue())], ["a.sol", "b.sol", "c.sol"])

    def call_cli(self, directory, *options):
        return subprocess.run([sys.executable, str(CLI), str(directory), *map(str, options)],
                              capture_output=True, text=True, timeout=45, cwd=ROOT)

    def results(self, completed):
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)  # 로그/두 번째 JSON이 붙으면 실패한다.
        Draft202012Validator.check_schema(SCHEMA)
        Draft202012Validator(SCHEMA).validate(data)
        self.assertTrue(all(item["reasons"] for item in data))
        return data

    def test_public_files_compile_and_schema(self):
        completed = self.call_cli(ROOT / "reference/public")
        data = self.results(completed)
        expected = sorted(p.name for p in (ROOT / "reference/public").glob("*.sol"))
        self.assertEqual([item["file"] for item in data], expected)
        self.assertEqual([item["verdict"] for item in data],
                         ["BENIGN", "MALICIOUS", "MALICIOUS", "BENIGN", "MALICIOUS"])
        self.assertIn("[1/5]", completed.stderr)

    def test_failure_then_success_and_direct_children_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shutil.copy(ROOT / "tests/fixtures/errors/invalid_syntax.sol", directory / "a.sol")
            shutil.copy(ROOT / "reference/public/P4_CappedMint.sol", directory / "z.sol")
            (directory / "ignored.txt").write_text("not Solidity")
            (directory / "nested").mkdir()
            (directory / "nested/hidden.sol").write_text("invalid")
            completed = self.call_cli(directory)
            data = self.results(completed)
            self.assertEqual([item["file"] for item in data], ["a.sol", "z.sol"])
            self.assertIn("구조 분석 실패", data[0]["reasons"][0])
            self.assertEqual(data[0]["verdict"], "UNCERTAIN")
            self.assertEqual(data[1]["verdict"], "BENIGN")
            self.assertIn("Expected type name", completed.stderr)

    def test_missing_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            for directory in (Path(temporary), Path(temporary) / "missing"):
                with self.subTest(directory=directory):
                    completed = self.call_cli(directory)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertEqual(completed.stdout, "")
                    self.assertTrue(completed.stderr)

    def test_missing_compiler(self):
        completed = self.call_cli(ROOT / "reference/public", "--solc", "/missing-trust1-solc")
        data = self.results(completed)
        self.assertEqual(len(data), 5)
        self.assertTrue(all("로컬 solc" in item["reasons"][0] for item in data))

    def test_total_budget_keeps_unprocessed_results(self):
        data = self.results(self.call_cli(ROOT / "reference/public", "--total-timeout", "0.000001"))
        self.assertEqual(len(data), 5)
        self.assertTrue(all("분석하지 못했습니다" in item["reasons"][0] for item in data))

    def test_timeout_kills_compiler_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            inputs = directory / "inputs"
            inputs.mkdir()
            shutil.copy(ROOT / "reference/public/P4_CappedMint.sol", inputs / "a.sol")
            marker = directory / "child.pid"
            fake = directory / "slow-solc"
            fake.write_text(
                f"#!{sys.executable}\n"
                "import subprocess, time\n"
                "from pathlib import Path\n"
                "child = subprocess.Popen(['/bin/sleep', '60'])\n"
                f"Path({str(marker)!r}).write_text(str(child.pid))\n"
                "time.sleep(60)\n"
            )
            fake.chmod(0o755)
            started = time.monotonic()
            # Allow Slither imports on a cold WSL filesystem before the fake
            # compiler starts. It still sleeps for 60s, so a 10s cutoff must kill it.
            data = self.results(self.call_cli(inputs, "--solc", fake, "--file-timeout", "10"))
            self.assertLess(time.monotonic() - started, 20)
            self.assertIn("시간 예산", data[0]["reasons"][0])
            self.assertTrue(marker.is_file(), "가짜 컴파일러까지 실제 실행되어야 한다")
            state = Path("/proc") / marker.read_text() / "stat"
            for _ in range(20):
                if not state.exists() or state.read_text().split()[2] == "Z":
                    break
                time.sleep(0.05)
            else:
                self.fail("timeout 뒤에도 컴파일러 자식이 실행 중")


if __name__ == "__main__":
    unittest.main(verbosity=2)
