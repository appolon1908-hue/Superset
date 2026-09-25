"""Superset stays business analytics: no observability backend, no OpenBao administration, secrets only as references."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("boundary", ROOT / "scripts" / "validate_monitoring_platform_boundary.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BoundaryTests(unittest.TestCase):
    def test_validator_passes(self) -> None:
        result = subprocess.run([sys.executable, "scripts/validate_monitoring_platform_boundary.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SUPERSET_OBSERVABILITY_BACKEND_CONNECTIONS=NONE", result.stdout)

    def test_boundary_forbids_every_non_analytics_role(self) -> None:
        boundary = json.loads((ROOT / "codestra/monitoring-platform-boundary.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(boundary["neverBecomes"]), {"prometheus-replacement", "log-database", "trace-backend", "openbao-administration-interface", "operational-database-writer"})
        self.assertEqual(boundary["identity"]["databaseRole"], "read-only")

    def test_value_bearing_reference_is_rejected(self) -> None:
        document = json.loads((ROOT / "codestra/secret-references.v1.json").read_text(encoding="utf-8"))
        poisoned = copy.deepcopy(document)
        poisoned["references"][0]["client_secret"] = "x"
        with self.assertRaises(SystemExit):
            MODULE.reject_secret_material(poisoned, "root")

    def test_observability_backend_connection_is_rejected(self) -> None:
        boundary = MODULE.validate_boundary()
        original = MODULE.ENV_EXAMPLE
        poisoned = ROOT / "codestra" / "runtime-v1" / "_poisoned.env"
        try:
            poisoned.write_text(original.read_text(encoding="utf-8") + "\nSUPERSET_EXTRA_DB=postgresql://reader@loki:3100/db\n", encoding="utf-8")
            MODULE.ENV_EXAMPLE = poisoned
            with self.assertRaises(SystemExit):
                MODULE.validate_runtime_sources(boundary)
        finally:
            MODULE.ENV_EXAMPLE = original
            poisoned.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
