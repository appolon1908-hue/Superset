from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseReadinessTests(unittest.TestCase):
    def test_upstream_tree_matches_lock(self) -> None:
        lock = json.loads((ROOT / "CODESTRA_UPSTREAM_LOCK.json").read_text())
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD:upstream"], cwd=ROOT, text=True
        ).strip()
        self.assertEqual(actual, lock["imported_tree_sha"])

    def test_bundle_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.tar.gz"
            second = Path(directory) / "second.tar.gz"
            for output in (first, second):
                subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/build_config_bundle.py"),
                        "--output",
                        str(output),
                    ],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).digest(),
                hashlib.sha256(second.read_bytes()).digest(),
            )

    def test_runtime_lock_never_activates_production(self) -> None:
        lock = json.loads(
            (ROOT / "codestra/release/runtime-image.lock.json").read_text()
        )
        self.assertFalse(lock["productionActivation"])
        self.assertIn("@sha256:", lock["image"])


if __name__ == "__main__":
    unittest.main()
