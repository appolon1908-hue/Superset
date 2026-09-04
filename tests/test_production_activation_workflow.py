from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github/workflows/release-image.yml"
BOUNDED_WORKFLOW = ROOT / ".github/workflows/bounded-runtime-certification.yml"
PREFLIGHT = ROOT / "scripts/production_runtime_preflight.sh"
DEPLOY = ROOT / "scripts/deploy_production.sh"
STAGING = ROOT / "scripts/run_disposable_integration.sh"
CANARY = ROOT / "scripts/run_production_readonly_canary.sh"
CANDIDATE = ROOT / "codestra/runtime-v1/compose.candidate.yaml"
INFRA = ROOT / "codestra/runtime-v1/compose.infrastructure.yaml"
SECURITY_MANAGER = ROOT / "codestra/runtime-v1/codestra_security_manager.py"
COMPAT_SECURITY_MANAGER = ROOT / "codestra/runtime-v1/codestra_security_manager_v2.py"


class ProductionActivationWorkflowTests(unittest.TestCase):
    def test_release_workflow_builds_and_verifies_without_runtime_mutation(self) -> None:
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "name: Release signed Superset image",
            "branches: [production]",
            "git rev-parse origin/production",
            "reusable-release-image.yml@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd",
            "scripts/verify_release_identity.sh",
            "cosign verify",
            "cosign verify-attestation",
            "gh attestation verify",
            "--signer-repo appolon1908-hue/Codestra-Telemetry",
            "--signer-digest 9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd",
            "superset-signed-release.json",
            "superset-signed-release.SHA256SUMS",
            "production_activation\": False",
            "gh release create",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "PRODUCTION_SSH_PRIVATE_KEY",
            "PRODUCTION_SSH_KNOWN_HOSTS",
            "scripts/production_runtime_preflight.sh",
            "scripts/deploy_production.sh",
            "ssh-keyscan",
            "StrictHostKeyChecking=no",
            "scp ",
            "ssh ",
            "--privileged",
            ":latest",
        ):
            self.assertNotIn(forbidden, text)

    def test_bounded_workflow_orders_release_staging_rollback_and_canary(self) -> None:
        text = BOUNDED_WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "workflow_run:",
            "Release signed Superset image",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.head_branch == 'production'",
            "release-policy:",
            "artifact-staging-certification:",
            "bounded-staging-runtime:",
            "runs-on: [self-hosted, codestra-staging]",
            "environment: staging-readonly",
            "production-readonly-canary:",
            "runs-on: [self-hosted, codestra-production-canary]",
            "environment: production-readonly-canary",
            "SUPERSET_CANARY_CONTROLLER_SHA256",
            "SUPERSET_CANARY_PERCENT",
            "scripts/run_disposable_integration.sh",
            "scripts/run_production_readonly_canary.sh",
            "staging_evidence_sha256",
            "SUPERSET_FULL_READONLY_CERTIFICATION=PASS",
        ):
            self.assertIn(token, text)
        self.assertLess(text.index("release-policy:"), text.index("artifact-staging-certification:"))
        self.assertLess(text.index("artifact-staging-certification:"), text.index("bounded-staging-runtime:"))
        self.assertLess(text.index("bounded-staging-runtime:"), text.index("production-readonly-canary:"))
        for forbidden in (
            "PRODUCTION_SSH_PRIVATE_KEY",
            "scripts/deploy_production.sh",
            "docker compose up",
            "systemctl restart",
            "-X POST",
        ):
            self.assertNotIn(forbidden, text)

    def test_staging_certifies_exact_signed_image_backup_restore_and_rollback(self) -> None:
        text = STAGING.read_text(encoding="utf-8")
        for token in (
            "supplied_image",
            "signed-immutable",
            "org.opencontainers.image.source",
            "org.opencontainers.image.revision",
            "10001:10001",
            "docker network create --internal",
            "superset db upgrade",
            "superset init",
            "bootstrap_roles.py",
            "pg_dump",
            "pg_restore --list",
            "superset_restore",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "SET ROLE analytics_readonly",
            "unauthorized-business",
            "read-only analytics role unexpectedly performed a write",
            "codestra.superset-bounded-staging-evidence.v1",
            "runtime_rollback_restart",
            "SUPERSET_BOUNDED_STAGING_ROLLBACK=PASS",
        ):
            self.assertIn(token, text)
        for forbidden in ("--network host", "--publish", "-p 0.0.0.0", "docker volume rm"):
            self.assertNotIn(forbidden, text)

    def test_production_canary_is_fixed_controller_read_only_and_self_rolling_back(self) -> None:
        text = CANARY.read_text(encoding="utf-8")
        for token in (
            "SUPERSET_CANARY_CONTROLLER",
            "SUPERSET_CANARY_CONTROLLER_SHA256",
            "codestra.superset-bounded-staging-evidence.v1",
            "--percent",
            "--methods GET,HEAD",
            "--read-only",
            "codestra.superset-readonly-canary-status.v1",
            "codestra.superset-readonly-canary-receipt.v1",
            "codestra.superset-readonly-canary-rollback.v1",
            "write_requests",
            "external_deliveries",
            "runtime_state_hash",
            "curl --fail --silent --show-error",
            "--head",
            "/api/v1/security/csrf_token/",
            "/swagger/v1",
            "rollback()",
            "runtime_restored_exactly",
            "SUPERSET_PRODUCTION_READONLY_CANARY=PASS",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "-X POST",
            "--request POST",
            "--data",
            "docker compose",
            "docker run",
            "systemctl",
            "sshd_config",
            "ufw ",
            "iptables ",
        ):
            self.assertNotIn(forbidden, text)

    def test_release_evidence_checksum_is_relative_and_verified(self) -> None:
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("sha256sum superset-signed-release.json > superset-signed-release.SHA256SUMS", text)
        bounded = BOUNDED_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("sha256sum --check superset-signed-release.SHA256SUMS", bounded)
        self.assertIn("release_evidence_sha256", bounded)

    def test_remote_preflight_remains_available_for_separate_activation_release(self) -> None:
        text = PREFLIGHT.read_text(encoding="utf-8")
        for token in (
            "docker_disk_below_8GiB",
            "memory_below_3GiB",
            "docker info --format '{{.DockerRootDir}}'",
            '"${docker_prefix[@]}" df -Pk "$docker_root"',
            "superset_dns_not_bound_to_expected_host",
            "keycloak_discovery_unavailable",
            "client_id=superset-analytics",
            "caddy_superset_route_missing",
            "loopback_port_owned_by_other_process",
            "existing_superset_loopback_unhealthy",
            "codestra-superset-corporate",
            "SUPERSET_PRODUCTION_PREFLIGHT=PASS",
        ):
            self.assertIn(token, text)
        self.assertNotIn("--location-trusted=false", text)

    def test_separate_deployment_script_has_backup_rollback_and_no_volume_deletion(self) -> None:
        text = DEPLOY.read_text(encoding="utf-8")
        for token in (
            "metadata-before-${source_sha}.dump",
            "pg_dump",
            "pg_restore --list",
            "superset-bootstrap",
            "check_metadata_readiness.py",
            "oidc_login_redirect_target_mismatch",
            "docker_auth_cmd()",
            'env DOCKER_CONFIG="$docker_config" docker',
            'as_root rm -rf -- "$docker_config"',
            'install -d -o "$run_uid" -g "$run_gid" -m 0750',
            'install -o "$run_uid" -g "$run_gid" -m 0640',
            "on_exit()",
            "rollback_runtime()",
            "SUPERSET_PRODUCTION_ROLLBACK=",
            "SUPERSET_PRODUCTION_DEPLOYMENT=PASS",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "docker volume rm",
            "down -v",
            "systemctl restart ssh",
            "sshd_config",
            "ufw ",
            "iptables ",
            'ghcr_token_b64=""',
            'oidc_secret_b64=""',
        ):
            self.assertNotIn(forbidden, text)

    def test_candidate_has_private_data_plane_explicit_egress_and_restarts(self) -> None:
        document = yaml.safe_load(CANDIDATE.read_text(encoding="utf-8"))
        self.assertTrue(document["networks"]["codestra-analytics"]["external"])
        self.assertTrue(document["networks"]["codestra-observability"]["external"])
        egress = document["networks"]["superset-egress"]
        self.assertEqual(egress["name"], "codestra-superset-egress")
        self.assertFalse(egress["internal"])
        self.assertEqual(egress["driver"], "bridge")
        for name in ("superset-web", "superset-worker", "superset-beat"):
            service = document["services"][name]
            self.assertEqual(service["restart"], "unless-stopped")
            self.assertIn("superset-egress", service["networks"])
        self.assertEqual(document["services"]["superset-bootstrap"]["restart"], "no")

    def test_infrastructure_uses_exact_images_and_private_services(self) -> None:
        document = yaml.safe_load(INFRA.read_text(encoding="utf-8"))
        self.assertEqual(set(document["services"]), {"superset-postgres", "superset-redis"})
        for service in document["services"].values():
            self.assertIn("@sha256:", service["image"])
            self.assertNotIn("ports", service)
            self.assertIn("ALL", service["cap_drop"])
            self.assertIn("no-new-privileges:true", service["security_opt"])
            self.assertEqual(
                set(service["cap_add"]),
                {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"},
            )
        self.assertTrue(document["services"]["superset-redis"]["read_only"])

    def test_keycloak_observability_roles_translate_only_to_global_roles(self) -> None:
        source = SECURITY_MANAGER.read_text(encoding="utf-8")
        compatibility = COMPAT_SECURITY_MANAGER.read_text(encoding="utf-8")
        self.assertEqual(source, compatibility)
        for token in (
            '"observability-viewer": {"superset-viewer"}',
            '"observability-operator": {"superset-analyst"}',
            '"observability-admin": {"superset-admin"}',
            "role_keys.update(KEYCLOAK_ROLE_ALIASES.get(claimed_role, set()))",
        ):
            self.assertIn(token, source)
        alias_block = source.split("KEYCLOAK_ROLE_ALIASES =", maxsplit=1)[1].split("\n}\n", maxsplit=1)[0]
        self.assertNotIn("business-", alias_block)


if __name__ == "__main__":
    unittest.main()
