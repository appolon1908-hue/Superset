#!/usr/bin/env python3
"""Validate Superset role, PKCE, template, and promotion-branch review fixes."""

from __future__ import annotations

import ast
import pathlib
import sys
from typing import Iterator

ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTIVE_CONFIG = ROOT / "codestra" / "runtime-v1" / "superset_config.py"
EXAMPLE_CONFIG = ROOT / "codestra" / "runtime-v1" / "superset_config.py.example"
PROFILE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "validate-codestra-enterprise-profile.yml"
)
BUSINESSES = (
    "codestra",
    "moneybee",
    "beyvra",
    "breero",
    "larim-a",
    "transportation",
    "booked4seasons",
    "social",
    "klyrow",
    "telnexa",
    "kyqra",
    "restaurant",
    "provisioning",
)


def fail(message: str) -> None:
    print(f"SUPERSET_REVIEW_HARDENING_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")


def parse(path: pathlib.Path) -> ast.Module:
    try:
        return ast.parse(read(path), filename=str(path))
    except SyntaxError as exc:
        fail(f"invalid Python {path.relative_to(ROOT)}: {exc}")


def dict_pairs(node: ast.Dict) -> Iterator[tuple[str, ast.AST]]:
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            yield key.value, value


def find_assignment(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
    fail(f"missing assignment {name}")


def find_remote_apps(tree: ast.Module) -> list[ast.Dict]:
    value = find_assignment(tree, "OAUTH_PROVIDERS")
    if not isinstance(value, ast.List):
        fail("OAUTH_PROVIDERS must be a list")
    remote_apps: list[ast.Dict] = []
    for provider in value.elts:
        if not isinstance(provider, ast.Dict):
            continue
        for key, child in dict_pairs(provider):
            if key == "remote_app" and isinstance(child, ast.Dict):
                remote_apps.append(child)
    return remote_apps


def validate_pkce(tree: ast.Module, label: str) -> None:
    remote_apps = find_remote_apps(tree)
    if len(remote_apps) != 1:
        fail(f"{label}: exactly one OAuth remote_app is required")
    remote = dict(dict_pairs(remote_apps[0]))
    pkce = remote.get("code_challenge_method")
    if not isinstance(pkce, ast.Constant) or pkce.value != "S256":
        fail(f"{label}: code_challenge_method must be direct remote_app S256")
    client_kwargs = remote.get("client_kwargs")
    if not isinstance(client_kwargs, ast.Dict):
        fail(f"{label}: client_kwargs must define OAuth scopes")
    if "code_challenge_method" in dict(dict_pairs(client_kwargs)):
        fail(f"{label}: PKCE may not be nested inside client_kwargs")


def validate_feature_flags(tree: ast.Module, label: str) -> None:
    value = find_assignment(tree, "FEATURE_FLAGS")
    if not isinstance(value, ast.Dict):
        fail(f"{label}: FEATURE_FLAGS must be a dict")
    flags = dict(dict_pairs(value))
    template = flags.get("ENABLE_TEMPLATE_PROCESSING")
    if not isinstance(template, ast.Constant) or template.value is not False:
        fail(f"{label}: ENABLE_TEMPLATE_PROCESSING must remain false")
    reports = flags.get("ALERT_REPORTS")
    if not isinstance(reports, ast.Constant) or reports.value is not False:
        fail(f"{label}: ALERT_REPORTS must remain false")


def validate_business_roles(text: str, label: str) -> None:
    required_fragments = (
        'f"business-{business}-viewer"',
        'f"business-{business}-analyst"',
        'f"Codestra Business {business} Viewer"',
        'f"Codestra Business {business} Analyst"',
    )
    for fragment in required_fragments:
        if fragment not in text:
            fail(f"{label}: business-specific role mapping missing {fragment}")
    forbidden = (
        'f"business-{business}-viewer": ["Gamma"]',
        'f"business-{business}-analyst": ["Alpha"]',
    )
    for fragment in forbidden:
        if fragment in text:
            fail(f"{label}: business identity is collapsed into shared base role")
    for business in BUSINESSES:
        if f'"{business}"' not in text:
            fail(f"{label}: business catalogue omits {business}")


def validate_workflow() -> None:
    text = read(PROFILE_WORKFLOW)
    for branch in ("development", "test", "staging", "production", "main"):
        if branch not in text:
            fail(f"enterprise-profile workflow omits promotion branch {branch}")
    if "validate-codestra-enterprise-profile.yml" not in text:
        fail("enterprise-profile workflow must self-trigger on workflow changes")


def main() -> None:
    for path, label in (
        (ACTIVE_CONFIG, "active config"),
        (EXAMPLE_CONFIG, "candidate config"),
    ):
        text = read(path)
        tree = parse(path)
        validate_pkce(tree, label)
        validate_feature_flags(tree, label)
        validate_business_roles(text, label)
    validate_workflow()
    print("CODESTRA_SUPERSET_REVIEW_HARDENING_PASS=1")


if __name__ == "__main__":
    main()
