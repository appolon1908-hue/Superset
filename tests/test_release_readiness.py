from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import tarfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_SOURCE_SHA = "1" * 40


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
                        "--source-revision",
                        TEST_SOURCE_SHA,
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

    def test_bundle_binds_the_protected_source_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bundle.tar.gz"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_config_bundle.py"),
                    "--output",
                    str(archive),
                    "--source-revision",
                    TEST_SOURCE_SHA,
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with tarfile.open(archive, "r:gz") as bundle:
                member = bundle.extractfile(
                    "codestra/runtime-v1/release-identity.json"
                )
                self.assertIsNotNone(member)
                identity = json.loads(member.read())
            self.assertEqual(identity["protectedSourceSha"], TEST_SOURCE_SHA)
            self.assertRegex(identity["runtimeImageDigest"], r"^sha256:[0-9a-f]{64}$")

    def test_runtime_lock_never_activates_production(self) -> None:
        lock = json.loads(
            (ROOT / "codestra/release/runtime-image.lock.json").read_text()
        )
        self.assertFalse(lock["productionActivation"])
        self.assertIn("@sha256:", lock["image"])


if __name__ == "__main__":
    unittest.main()
