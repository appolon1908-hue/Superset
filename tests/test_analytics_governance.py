from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AnalyticsGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.governance = json.loads(
            (ROOT / "codestra/runtime-v1/analytics-governance.json").read_text()
        )
        cls.control = json.loads(
            (
                ROOT
                / "codestra/runtime-v1/analytics-control-plane.v1.json"
            ).read_text()
        )

    def test_every_certified_dataset_has_release_metadata(self) -> None:
        for dataset in self.governance["certifiedDatasets"]:
            with self.subTest(dataset=dataset["name"]):
                self.assertTrue(dataset["owner"])
                self.assertTrue(dataset["sourceLineage"].startswith("approved-reporting."))
                self.assertGreater(dataset["freshnessSlaMinutes"], 0)
                self.assertTrue(dataset["sensitivity"])
                self.assertTrue(dataset["readOnly"])

    def test_forbidden_sensitive_fields_are_explicit(self) -> None:
        fields = set(self.governance["forbiddenColumns"])
        self.assertTrue(
            {
                "password",
                "secret",
                "access_token",
                "private_key",
                "email_body",
                "sms_body",
                "raw_request_body",
                "raw_response_body",
            }.issubset(fields)
        )

    def test_dashboard_ownership_is_complete(self) -> None:
        for dashboard in self.control["dashboardCatalogue"]:
            with self.subTest(dashboard=dashboard.get("id", dashboard.get("idPattern"))):
                self.assertTrue(dashboard["owner"])
                self.assertTrue(dashboard["requiredSections"])

    def test_repository_does_not_claim_live_governance_evidence(self) -> None:
        self.assertTrue(
            all(value is False for value in self.control["releaseGates"].values())
        )


if __name__ == "__main__":
    unittest.main()
