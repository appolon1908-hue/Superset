from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release-image.yml"
PREFLIGHT = ROOT / "scripts/production_runtime_preflight.sh"
DEPLOY = ROOT / "scripts/deploy_production.sh"
CANDIDATE = ROOT / "codestra/runtime-v1/compose.candidate.yaml"
INFRA = ROOT / "codestra/runtime-v1/compose.infrastructure.yaml"
SECURITY_MANAGER = ROOT / "codestra/runtime-v1/codestra_security_manager.py"
COMPAT_SECURITY_MANAGER = (
    ROOT / "codestra/runtime-v1/codestra_security_manager_v2.py"
)


class ProductionActivationWorkflowTests(unittest.TestCase):
    def test_release_and_deploy_workflow_is_fail_closed(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "refs/heads/production",
            "git rev-parse origin/production",
            "PRODUCTION_SSH_PRIVATE_KEY",
            "PRODUCTION_SSH_KNOWN_HOSTS",
            "StrictHostKeyChecking=yes",
            "scripts/production_runtime_preflight.sh",
            "reusable-release-image.yml@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd",
            "gh attestation verify",
            "--signer-repo appolon1908-hue/Codestra-Telemetry",
            "--signer-workflow appolon1908-hue/Codestra-Telemetry/.github/workflows/reusable-release-image.yml",
            "--signer-digest 9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd",
            "--deny-self-hosted-runners",
            "scripts/verify_release_identity.sh",
            "scripts/deploy_production.sh",
            "superset-production-activation-",
            "https://supe.codestra.media/health",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "ssh-keyscan",
            "StrictHostKeyChecking=no",
            "--privileged",
            "network_mode: host",
            ":latest",
        ):
            self.assertNotIn(forbidden, text)

    def test_package_checksums_are_portable_and_relative(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cd "$package_root"', text)
        self.assertIn('cd "$RUNNER_TEMP"', text)
        self.assertIn('sha256sum "$archive_name" > "${archive_name}.sha256"', text)
        self.assertIn("sha256sum --check package.sha256", text)
        self.assertNotIn('sha256sum "$package_root"/*', text)
        self.assertNotIn('sha256sum "$archive" > "${archive}.sha256"', text)

    def test_remote_preflight_checks_identity_route_and_capacity(self) -> None:
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

    def test_deployment_has_backup_rollback_and_no_volume_deletion(self) -> None:
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
        self.assertEqual(
            set(document["services"]), {"superset-postgres", "superset-redis"}
        )
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
        alias_block = source.split("KEYCLOAK_ROLE_ALIASES =", maxsplit=1)[1].split(
            "\n}\n", maxsplit=1
        )[0]
        self.assertNotIn("business-", alias_block)


if __name__ == "__main__":
    unittest.main()
