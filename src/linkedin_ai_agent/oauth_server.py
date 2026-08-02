from __future__ import annotations

import json
import secrets
import threading
import webbrowser
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from .config import AgentConfig
from .linkedin_client import authorization_url, exchange_code_for_token, linkedin_token_expires_at


def run_local_oauth(config: AgentConfig, host: str = "127.0.0.1", port: int = 8080) -> dict[str, Any]:
    redirect_uri = f"http://{host}:{port}/callback"
    state = secrets.token_urlsafe(24)
    result: dict[str, Any] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            params = parse_qs(parsed.query)
            if params.get("state", [""])[0] != state:
                self._respond(400, "State mismatch. Close this tab and rerun auth-local.")
                done.set()
                return
            if "error" in params:
                result["error"] = params.get("error_description", params["error"])[0]
                self._respond(400, "LinkedIn authorization failed. Return to the terminal.")
                done.set()
                return
            code = params.get("code", [""])[0]
            if not code:
                self._respond(400, "Missing authorization code. Return to the terminal.")
                done.set()
                return
            try:
                token = exchange_code_for_token(code, redirect_uri)
                token["expires_at"] = linkedin_token_expires_at(token)
                owner_urn = owner_urn_from_id_token(str(token.get("id_token", "")))
                if owner_urn:
                    token["owner_urn"] = owner_urn
                    write_owner_urn_to_config(owner_urn)
                result["token"] = token
                config.state_dir.mkdir(parents=True, exist_ok=True)
                (config.state_dir / "linkedin_token_metadata.json").write_text(
                    json.dumps({"expires_at": token["expires_at"]}, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                self._respond(200, "LinkedIn authorization complete. You can close this tab and return to the terminal.")
            except Exception as exc:
                result["error"] = str(exc)
                self._respond(500, "Token exchange failed. Return to the terminal.")
            finally:
                done.set()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _respond(self, status: int, message: str) -> None:
            body = f"<html><body><h1>{message}</h1></body></html>".encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((host, port), Handler)
    try:
        webbrowser.open(authorization_url(redirect_uri, state))
        while not done.is_set():
            server.handle_request()
    finally:
        server.server_close()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["token"]


def owner_urn_from_id_token(id_token: str) -> str | None:
    parts = id_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    subject = data.get("sub")
    if not subject:
        return None
    return f"urn:li:person:{subject}"


def write_owner_urn_to_config(owner_urn: str, path: str = "config/agent.yaml") -> None:
    config_path = __import__("pathlib").Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    linkedin = data.setdefault("linkedin", {})
    linkedin["owner_urn"] = owner_urn
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
