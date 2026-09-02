from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReadinessTests(unittest.TestCase):
    def test_validator(self) -> None:
        subprocess.run(
            ["python3", "scripts/validate_repository_readiness.py"],
            cwd=ROOT,
            check=True,
        )

    def test_runtime_and_release_gates_remain_false(self) -> None:
        runtime = json.loads(
            (ROOT / "codestra/runtime-v1/runtime.v1.json").read_text()
        )
        control = json.loads(
            (
                ROOT
                / "codestra/runtime-v1/analytics-control-plane.v1.json"
            ).read_text()
        )
        self.assertTrue(
            all(value is False for value in runtime["activation"].values())
        )
        self.assertTrue(
            all(value is False for value in control["releaseGates"].values())
        )

    def test_compose_is_canonical_and_file_secret_bound(self) -> None:
        self.assertFalse((ROOT / "codestra/runtime-v1/compose.yaml").exists())
        compose = yaml.safe_load(
            (ROOT / "codestra/runtime-v1/compose.candidate.yaml").read_text()
        )
        self.assertEqual(
            set(compose["services"]),
            {
                "superset-web",
                "superset-worker",
                "superset-beat",
                "superset-bootstrap",
            },
        )
        self.assertTrue(
            all(set(value) == {"file"} for value in compose["secrets"].values())
        )

    def test_runtime_identity_rejects_mutable_or_misaligned_images(self) -> None:
        environment = dict(os.environ)
        environment.update(
            CODESTRA_SOURCE_SHA="0" * 40,
            CODESTRA_IMAGE_DIGEST="sha256:" + "2" * 64,
        )
        for image in (
            "ghcr.io/appolon1908-hue/superset-superset:latest",
            "ghcr.io/appolon1908-hue/superset-superset@sha256:" + "1" * 64,
        ):
            result = subprocess.run(
                ["python3", "scripts/validate_runtime_identity.py"],
                cwd=ROOT,
                env={**environment, "CODESTRA_SUPERSET_IMAGE": image},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_upstream_tree_lock_matches_repository(self) -> None:
        lock = json.loads((ROOT / "CODESTRA_UPSTREAM_LOCK.json").read_text())
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD:upstream"],
            cwd=ROOT,
            text=True,
        ).strip()
        self.assertEqual(lock["schema_version"], "1.1")
        self.assertTrue(lock["source_tree_verification"])
        self.assertEqual(actual, lock["imported_tree_sha"])

    def test_bootstrap_uses_application_factory_and_runtime_gate(self) -> None:
        bootstrap = (
            ROOT / "codestra/runtime-v1/bootstrap_roles.py"
        ).read_text(encoding="utf-8")
        inspection = (
            ROOT / "scripts/build_and_inspect_locked_image.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from superset import app", bootstrap)
        self.assertIn("from superset.app import create_app", bootstrap)
        self.assertIn("application = create_app()", bootstrap)
        self.assertIn("with application.app_context():", bootstrap)
        self.assertGreaterEqual(
            inspection.count("python /app/pythonpath/bootstrap_roles.py"),
            2,
        )
        self.assertIn("tests/validate_bootstrap_runtime.py", inspection)
        self.assertIn("tests/validate_celery_runtime.py", inspection)

    def test_oauth_runtime_dependency_is_exact_and_hash_locked(self) -> None:
        oauth_input = (ROOT / "requirements-oauth.in").read_text().splitlines()
        oauth_lock = (ROOT / "requirements-oauth.txt").read_text()
        dockerfile = (
            ROOT / "codestra/runtime-v1/Dockerfile"
        ).read_text(encoding="utf-8")
        self.assertEqual(oauth_input, ["authlib==1.6.12"])
        self.assertEqual(
            set(re.findall(r"--hash=sha256:([0-9a-f]{64})", oauth_lock)),
            {
                "0656d8482f28fc8221929d5f35b2bde5d13e10555ebc06b4561b0d622e83b1bd",
                "e9229ad7fde610b139dd12f5edbe97eab9ee78bfb85691247e767727850b99ab",
            },
        )
        self.assertIn("requirements-oauth.txt", dockerfile)
        self.assertIn("--no-deps", dockerfile)
        self.assertIn('metadata.version("authlib") == "1.6.12"', dockerfile)
        self.assertIn('metadata.version("cryptography") == "46.0.5"', dockerfile)

    def test_disposable_integration_is_private_and_secret_safe(self) -> None:
        integration = (
            ROOT / "scripts/run_disposable_integration.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("docker network create --internal", integration)
        self.assertIn("install -d -m 0711", integration)
        self.assertNotIn("mkdir -m 0700", integration)
        self.assertNotIn("install -d -m 0700", integration)
        self.assertNotIn("--network host", integration)
        self.assertNotIn("--publish", integration)
        self.assertIn("chmod 0444", integration)
        self.assertGreaterEqual(
            integration.count("python /app/pythonpath/bootstrap_roles.py"),
            2,
        )
        for token in (
            "pg_dump",
            "pg_restore",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "unauthorized-business",
            "validate_celery_runtime.py",
        ):
            self.assertIn(token, integration)

    def test_release_identity_is_digest_and_revision_bound(self) -> None:
        source = (
            ROOT / "scripts/verify_release_identity.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("superset-superset@sha256:", source)
        self.assertIn("org.opencontainers.image.source", source)
        self.assertIn("org.opencontainers.image.revision", source)
        self.assertIn(".RepoDigests", source)
        self.assertIn("10001:10001", source)
        self.assertNotIn(":latest", source)


if __name__ == "__main__":
    unittest.main()
