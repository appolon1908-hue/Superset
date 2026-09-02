from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SecurityManagerSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "codestra/runtime-v1/codestra_security_manager.py"
        cls.source = cls.path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_userinfo_is_issuer_bound(self) -> None:
        self.assertIn('os.environ["KEYCLOAK_ISSUER"]', self.source)
        self.assertIn("/protocol/openid-connect/userinfo", self.source)
        self.assertNotIn('remote.get("userinfo")', self.source)

    def test_identity_checks_fail_closed(self) -> None:
        for fragment in (
            'provider != "keycloak"',
            'email_verified") is not True',
            "No approved Codestra Superset role was supplied",
        ):
            self.assertIn(fragment, self.source)

    def test_only_approved_role_keys_are_returned(self) -> None:
        self.assertIn("& APPROVED_ROLE_KEYS", self.source)
        self.assertIn('"role_keys": role_keys', self.source)


if __name__ == "__main__":
    unittest.main()
