#!/usr/bin/env python3
"""Fail-closed validation of Superset's boundary in the monitoring platform.

Superset is business analytics over curated read-only projections. This
validator proves from source that it never points a database connection at
Prometheus, Loki, Tempo, Alertmanager, OpenBao or the Middleware runtime, that
no OpenBao administrative address or token variable exists in its runtime
configuration, that every secret it reads is a file rendered from an OpenBao
secret reference held by the read-only superset-analytics identity, and that
the analytics control plane keeps read-only connections mandatory.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CODESTRA = ROOT / "codestra"
RUNTIME = CODESTRA / "runtime-v1"
BOUNDARY = CODESTRA / "monitoring-platform-boundary.v1.json"
SECRET_REFERENCES = CODESTRA / "secret-references.v1.json"
SECRET_SCHEMA = CODESTRA / "contracts" / "secret-reference.v1.schema.json"
SECRET_SCHEMA_PIN = CODESTRA / "contracts" / "secret-reference.v1.schema.sha256"
CONTROL_PLANE = RUNTIME / "analytics-control-plane.v1.json"
CONFIG = RUNTIME / "superset_config.py"
COMPOSE = RUNTIME / "compose.candidate.yaml"
ENV_EXAMPLE = RUNTIME / "runtime.env.example"
FORBIDDEN_REFERENCE_KEYS = {
    "value", "password", "token", "private_key", "client_secret", "secret",
    "secret_value", "unseal_key", "recovery_key", "root_token",
}


def fail(message: str) -> None:
    print(f"SUPERSET_MONITORING_BOUNDARY=FAIL {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")


def validate_boundary() -> dict[str, Any]:
    boundary = load_json(BOUNDARY)
    if boundary.get("role") != "business-analytics-only" or boundary.get("readOnlyConnectionRequired") is not True:
        fail("Superset must remain read-only business analytics")
    for never in ("prometheus-replacement", "log-database", "trace-backend", "openbao-administration-interface", "operational-database-writer"):
        if never not in boundary.get("neverBecomes", []):
            fail(f"boundary must forbid becoming {never}")
    identity = boundary.get("identity", {})
    if identity.get("openbaoWorkloadIdentity") != "superset-analytics" or identity.get("databaseRole") != "read-only":
        fail("Superset must use the read-only superset-analytics identity")
    if boundary.get("runtimeApplyAuthorized") is not False:
        fail("boundary must not authorize runtime apply")
    return boundary


def validate_runtime_sources(boundary: dict[str, Any]) -> None:
    texts = {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8") for path in (CONFIG, COMPOSE, ENV_EXAMPLE)}
    hosts = boundary["forbiddenDatasourceHosts"]
    for name, text in texts.items():
        for host in hosts:
            if re.search(rf"(?i)(postgresql|mysql|sqlite|trino|presto|clickhouse|https?)(\+[a-z0-9]+)?://[^\s\"']*\b{re.escape(host)}\b", text):
                fail(f"{name} points a connection at the forbidden host {host}")
        for variable in boundary["forbiddenEnvironmentVariables"]:
            if re.search(rf"(?m)^\s*{re.escape(variable)}\s*[:=]", text):
                fail(f"{name} configures the OpenBao administrative variable {variable}")
        if re.search(r"(?im)^\s*[A-Z0-9_]*(PASSWORD|SECRET|TOKEN)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_.-]{16,}\s*$", text):
            fail(f"{name} carries an inline credential")
    config = texts["codestra/runtime-v1/superset_config.py"]
    for required in ("SUPERSET_SECRET_KEY_FILE", "SUPERSET_METADATA_DATABASE_URI_FILE", "SUPERSET_OIDC_CLIENT_SECRET_FILE"):
        if f'read_secret("{required}")' not in config:
            fail(f"superset_config.py must read {required} from a rendered file")
    control_plane = load_json(CONTROL_PLANE)
    requirements = control_plane.get("datasetRequirements", {})
    if requirements.get("readOnlyConnectionRequired") is not True or requirements.get("reportingSchemaOrReplicaRequired") is not True:
        fail("analytics datasets must use read-only connections on the reporting schema or replica")


def reject_secret_material(value: Any, trail: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_REFERENCE_KEYS or str(key).lower().endswith(("_password", "_token", "_secret")):
                fail(f"secret reference carries a value-bearing key at {trail}.{key}")
            reject_secret_material(item, f"{trail}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{trail}[{index}]")
    elif isinstance(value, str) and (value.startswith("hvs.") or ("PRIVATE " + "KEY") in value):
        fail(f"secret-shaped value at {trail}")


def validate_secret_references() -> None:
    schema = load_json(SECRET_SCHEMA)
    pin = SECRET_SCHEMA_PIN.read_text(encoding="utf-8").strip()
    if hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() != pin:
        fail("vendored secret-reference schema does not match its pin")
    document = load_json(SECRET_REFERENCES)
    if document.get("secretValuesIncluded") is not False or document.get("schemaSha256") != pin:
        fail("secret references must declare no values and bind the pinned schema")
    if document.get("authority", {}).get("workloadIdentity") != "superset-analytics":
        fail("Superset reads OpenBao only as the superset-analytics identity")
    reject_secret_material(document, "secret-references")
    covered: set[str] = set()
    environments: set[str] = set()
    for index, reference in enumerate(document.get("references", [])):
        trail = f"references[{index}]"
        for required in schema["required"]:
            if required not in reference:
                fail(f"{trail} missing {required}")
        env = reference["environment"]
        if not reference["secret_ref"].startswith(f"codestra/{env}/analytics/superset/") or reference["workload_identity"] != "superset-analytics":
            fail(f"{trail} must lie beneath the superset-analytics prefix for {env}")
        if reference.get("reference_uri") != "openbao://" + reference["secret_ref"]:
            fail(f"{trail} reference_uri must equal openbao:// + secret_ref")
        if reference["secret_class"] not in schema["properties"]["secret_class"]["enum"]:
            fail(f"{trail} has an unknown secret_class")
        environments.add(env)
        covered.update(reference.get("runtime_files", []))
    if environments != {"staging", "production"}:
        fail("secret references must cover exactly staging and production")
    for path in (COMPOSE, ENV_EXAMPLE):
        for secret_file in sorted(set(re.findall(r"/run/secrets/[A-Za-z0-9_./-]+", path.read_text(encoding="utf-8")))):
            if secret_file not in covered:
                fail(f"{path.relative_to(ROOT)} reads {secret_file} without an OpenBao secret reference")


def main() -> None:
    boundary = validate_boundary()
    validate_runtime_sources(boundary)
    validate_secret_references()
    print("SUPERSET_MONITORING_BOUNDARY=PASS")
    print("SUPERSET_OBSERVABILITY_BACKEND_CONNECTIONS=NONE")
    print("SUPERSET_OPENBAO_ADMINISTRATION=NONE")
    print("SUPERSET_SECRET_VALUES_IN_SOURCE=NONE")


if __name__ == "__main__":
    main()
