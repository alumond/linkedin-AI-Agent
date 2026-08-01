from __future__ import annotations

import os
import socket
from dataclasses import dataclass


REQUIRED_HOSTS = (
    "generativelanguage.googleapis.com",
    "api.linkedin.com",
)


@dataclass
class PreflightResult:
    passed: bool
    checks: list[dict[str, str]]


def run_preflight(require_linkedin_token: bool = False) -> PreflightResult:
    checks: list[dict[str, str]] = []
    checks.append(_env_check("GEMINI_API_KEY"))
    checks.append(_env_check("LINKEDIN_CLIENT_ID"))
    checks.append(_env_check("LINKEDIN_CLIENT_SECRET"))
    if require_linkedin_token:
        checks.append(_env_check("LINKEDIN_ACCESS_TOKEN"))
    for host in REQUIRED_HOSTS:
        checks.append(_dns_check(host))
    return PreflightResult(passed=all(item["status"] == "ok" for item in checks), checks=checks)


def _env_check(name: str) -> dict[str, str]:
    return {
        "check": f"env:{name}",
        "status": "ok" if os.environ.get(name) else "missing",
        "message": "set" if os.environ.get(name) else "not set in this terminal",
    }


def _dns_check(host: str) -> dict[str, str]:
    try:
        socket.getaddrinfo(host, 443)
    except OSError as exc:
        return {"check": f"dns:{host}", "status": "failed", "message": str(exc)}
    return {"check": f"dns:{host}", "status": "ok", "message": "resolves"}
