from __future__ import annotations
import json
import os
import subprocess
import tempfile
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

    def test_security_and_worker_configuration_preserves_runtime_contracts(self) -> None:
        config = (ROOT / "codestra/runtime-v1/superset_config.py").read_text()
        self.assertIn('"force_https": False', config)
        self.assertIn('"content_security_policy_nonce_in": ["script-src"]', config)
        self.assertIn('"superset.sql_lab"', config)
        self.assertIn('"sql_lab.get_sql_results"', config)
        self.assertIn('"deletion_retention.purge_soft_deleted"', config)
        bootstrap = (ROOT / "codestra/runtime-v1/bootstrap_roles.py").read_text()
        self.assertIn("from superset.app import create_app", bootstrap)
        self.assertIn("app = create_app()", bootstrap)

    def test_release_identity_gate_is_fail_closed(self) -> None:
        source = (ROOT / "scripts/verify_release_identity.sh").read_text()
        self.assertIn("org.opencontainers.image.revision", source)
        self.assertIn(".RepoDigests", source)
        self.assertNotIn(":latest", source)

    def test_release_identity_gate_binds_digest_and_revision(self) -> None:
        digest = "3" * 64
        source_sha = "4" * 40
        image = f"ghcr.io/appolon1908-hue/superset-superset@sha256:{digest}"
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "docker"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *org.opencontainers.image.source*) echo https://github.com/appolon1908-hue/Superset ;;\n"
                "  *org.opencontainers.image.revision*) echo \"$FAKE_SOURCE_SHA\" ;;\n"
                "  *Config.User*) echo 10001:10001 ;;\n"
                "  *RepoDigests*) printf '[\"%s\"]\\n' \"$FAKE_IMAGE\" ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n"
            )
            fake.chmod(0o755)
            environment = dict(os.environ)
            environment.update(
                PATH=f"{directory}:{environment['PATH']}",
                FAKE_IMAGE=image,
                FAKE_SOURCE_SHA=source_sha,
            )
            subprocess.run(
                ["bash", "scripts/verify_release_identity.sh", image, source_sha],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_disposable_database_gate_keeps_stdin_and_denies_external_runtime(self) -> None:
        source = (ROOT / "scripts/run_disposable_integration.sh").read_text()
        self.assertIn("docker network create --internal", source)
        self.assertIn('docker exec -i "$postgres" psql', source)
        self.assertIn("superset db upgrade", source)
        self.assertIn("pg_restore", source)
        self.assertIn("ALTER TABLE certified_dataset FORCE ROW LEVEL SECURITY", source)
        self.assertIn('chmod 0555 "$secret_root"', source)
        self.assertIn('chmod 0700 "$secret_root"', source)
        self.assertIn("authlib==1.6.12", (ROOT / "requirements-runtime.in").read_text())

if __name__ == "__main__":
    unittest.main()
