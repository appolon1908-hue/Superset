"""Superset keeps no Middleware V3 command, mutation, write or secret authority (Lane E audit record)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "codestra" / "contracts" / "middleware-v3-analytics-boundary.v1.json"
BOUNDARY = ROOT / "codestra" / "monitoring-platform-boundary.v1.json"
CONTROL_PLANE = ROOT / "codestra" / "runtime-v1" / "analytics-control-plane.v1.json"
CONFIG = ROOT / "codestra" / "runtime-v1" / "superset_config.py"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class AnalyticsBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load(CONTRACT)
        cls.boundary = load(BOUNDARY)
        cls.control_plane = load(CONTROL_PLANE)
        cls.config = CONFIG.read_text(encoding="utf-8")

    def test_contract_is_dark_and_pinned(self) -> None:
        self.assertEqual(self.contract["status"], "PREPARED_DISABLED")
        self.assertFalse(self.contract["activation_enabled"])
        self.assertEqual(self.contract["middleware"]["prep_base_sha"], "22d023a9c65b0789a0f7ee6c28548753521a9eff")
        self.assertRegex(self.contract["middleware"]["v3_final_sha"], r"^(PENDING|[0-9a-f]{40})$")

    def test_no_middleware_v3_authority(self) -> None:
        audit = self.contract["audit"]
        for key in ("middleware_v3_command_authority", "command_execution", "provider_mutation", "operational_writes", "secret_resolution_authority"):
            self.assertIs(audit[key], False, key)

    def test_boundary_forbids_operational_backends(self) -> None:
        self.assertEqual(self.boundary["role"], "business-analytics-only")
        hosts = set(self.boundary["forbiddenDatasourceHosts"])
        self.assertTrue({"middleware-integration-api", "openbao", "prometheus", "loki", "tempo", "alertmanager"} <= hosts)
        self.assertTrue({"BAO_TOKEN", "VAULT_TOKEN", "OPENBAO_TOKEN"} <= set(self.boundary["forbiddenEnvironmentVariables"]))
        self.assertTrue(self.boundary["readOnlyConnectionRequired"])
        self.assertFalse(self.boundary["runtimeApplyAuthorized"])
        self.assertEqual(self.boundary["identity"]["databaseRole"], "read-only")

    def test_control_plane_has_no_dml(self) -> None:
        flags: list[bool] = []

        def walk(value) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "writeDmlOrDdl":
                        flags.append(item)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(self.control_plane)
        self.assertTrue(flags, "analytics-control-plane must declare writeDmlOrDdl")
        self.assertTrue(all(flag is False for flag in flags))

    def test_runtime_config_keeps_effect_paths_off(self) -> None:
        flags = re.search(r"FEATURE_FLAGS\s*=\s*\{(.*?)\}", self.config, flags=re.DOTALL)
        assert flags is not None
        for flag in ("ALERT_REPORTS", "ENABLE_TEMPLATE_PROCESSING", "EMBEDDED_SUPERSET"):
            self.assertRegex(flags.group(1), rf'"{flag}":\s*False', flag)
        self.assertIn("PREVENT_UNSAFE_DB_CONNECTIONS = True", self.config)
        self.assertIn("AUTH_TYPE = AUTH_OAUTH", self.config)
        self.assertIn("PUBLIC_ROLE_LIKE = None", self.config)
        self.assertNotRegex(self.config, r"(?m)^\s*ALLOW_DML\s*=\s*True")
        self.assertNotRegex(self.config, r"middleware-integration-api|bao\.codestra\.media|BAO_TOKEN|VAULT_TOKEN")
        self.assertRegex(self.config, r'SQLALCHEMY_DATABASE_URI\s*=\s*read_secret\(')


if __name__ == "__main__":
    unittest.main()
