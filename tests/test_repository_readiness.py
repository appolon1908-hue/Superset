from __future__ import annotations
import json
import os
import subprocess
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class ReadinessTests(unittest.TestCase):
    def test_validator(self) -> None:
        subprocess.run(["python3", "scripts/validate_repository_readiness.py"], cwd=ROOT, check=True)

    def test_runtime_and_release_gates_remain_false(self) -> None:
        runtime = json.loads((ROOT / "codestra/runtime-v1/runtime.v1.json").read_text())
        control = json.loads((ROOT / "codestra/runtime-v1/analytics-control-plane.v1.json").read_text())
        self.assertTrue(all(value is False for value in runtime["activation"].values()))
        self.assertTrue(all(value is False for value in control["releaseGates"].values()))

    def test_compose_is_canonical_and_file_secret_bound(self) -> None:
        self.assertFalse((ROOT / "codestra/runtime-v1/compose.yaml").exists())
        compose = yaml.safe_load((ROOT / "codestra/runtime-v1/compose.candidate.yaml").read_text())
        self.assertEqual(
            set(compose["services"]),
            {"superset-web", "superset-worker", "superset-beat", "superset-bootstrap"},
        )
        self.assertTrue(all(set(value) == {"file"} for value in compose["secrets"].values()))

    def test_runtime_identity_rejects_mutable_or_misaligned_images(self) -> None:
        environment = dict(os.environ)
        environment.update(CODESTRA_SOURCE_SHA="0" * 40, CODESTRA_IMAGE_DIGEST="sha256:" + "2" * 64)
        for image in (
            "ghcr.io/appolon1908-hue/superset-superset:latest",
            "ghcr.io/appolon1908-hue/superset-superset@sha256:" + "1" * 64,
        ):
            result = subprocess.run(
                ["python3", "scripts/validate_runtime_identity.py"], cwd=ROOT,
                env={**environment, "CODESTRA_SUPERSET_IMAGE": image}, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__":
    unittest.main()
