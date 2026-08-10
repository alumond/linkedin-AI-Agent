from __future__ import annotations

import argparse
import json
import secrets
import sys

from .agent import LinkedInAIAgent, token_metadata
from .config import load_config, public_config
from .history import PublicationHistory
from .linkedin_client import LinkedInClient, authorization_url, exchange_code_for_token
from .models import to_dict
from .oauth_server import run_local_oauth
from .preflight import run_preflight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="linkedin-ai-agent")
    parser.add_argument("--config", default="config/agent.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth")
    auth.add_argument("--redirect-uri", required=True)
    auth.add_argument("--code")

    auth_local = sub.add_parser("auth-local")
    auth_local.add_argument("--host", default="127.0.0.1")
    auth_local.add_argument("--port", type=int, default=8080)

    sub.add_parser("research")
    sub.add_parser("generate")
    sub.add_parser("preview")
    publish_preview = sub.add_parser("publish-preview")
    publish_preview.add_argument("--confirm", action="store_true")

    run = sub.add_parser("run")
    run.add_argument("--dry-run", action="store_true")

    featured = sub.add_parser("featured-dashboard")
    featured.add_argument("--dry-run", action="store_true")

    sub.add_parser("token-status")
    sub.add_parser("whoami")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--live", action="store_true")
    sub.add_parser("show-config")

    args = parser.parse_args(argv)
    config = load_config(args.config)
    agent = LinkedInAIAgent(config)

    if args.command == "auth":
        if not args.code:
            state = secrets.token_urlsafe(24)
            print("Open this URL, approve LinkedIn access, then rerun auth with --code:")
            print(authorization_url(args.redirect_uri, state))
            print(f"OAuth state: {state}")
            return 0
        token = exchange_code_for_token(args.code, args.redirect_uri)
        expires_in = int(token.get("expires_in", 60 * 60 * 24 * 60))
        metadata = token_metadata(expires_in)
        config.state_dir.mkdir(parents=True, exist_ok=True)
        (config.state_dir / "linkedin_token_metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print("Token exchange succeeded. Store this value as LINKEDIN_ACCESS_TOKEN in your secret manager:")
        print(token.get("access_token", ""))
        print(f"Token metadata written to {config.state_dir / 'linkedin_token_metadata.json'}")
        return 0

    if args.command == "auth-local":
        token = run_local_oauth(config, host=args.host, port=args.port)
        print("LinkedIn OAuth succeeded. Store this as LINKEDIN_ACCESS_TOKEN:")
        print(token.get("access_token", ""))
        print(f"Token expires at: {token.get('expires_at')}")
        if token.get("owner_urn"):
            print(f"LinkedIn owner URN saved to config/agent.yaml: {token.get('owner_urn')}")
        return 0

    if args.command == "research":
        candidates, citations = agent.research()
        print(json.dumps({"candidates": to_dict(candidates), "citations": citations}, indent=2))
        return 0

    if args.command == "generate":
        candidates, citations = agent.research()
        if not candidates:
            print(json.dumps({"status": "skipped", "reason": "No candidate passed research gates.", "citations": citations}, indent=2))
            return 2
        draft, visual = agent.generate(candidates[0])
        print(json.dumps({"draft": to_dict(draft), "visual": to_dict(visual), "citations": citations}, indent=2))
        return 0

    if args.command == "preview":
        try:
            candidates, citations, diagnostics = agent.research_with_diagnostics()
            if not candidates:
                print(
                    json.dumps(
                        {
                            "status": "skipped",
                            "reason": "No candidate passed research gates.",
                            "rejected_candidates": diagnostics,
                            "citations": compact_citations(citations),
                        },
                        indent=2,
                    )
                )
                return 2
            draft, visual = agent.generate(candidates[0])
        except Exception as exc:
            print(json.dumps({"status": "skipped", "reason": str(exc)}, indent=2))
            return 2
        stage_path = agent.stage_preview(draft, visual, compact_citations(citations))
        print_preview(draft, visual, citations, stage_path)
        return 0

    if args.command == "publish-preview":
        if not args.confirm:
            print("Nothing was published. Review the preview, then rerun with --confirm.")
            return 2
        token = agent.token_status()
        if token.get("status") in {"missing", "expired"}:
            print(json.dumps({"status": "skipped", "reason": "LinkedIn token metadata is missing or expired.", "token": token}, indent=2))
            return 2
        try:
            result = agent.publish_staged()
        except Exception as exc:
            print(json.dumps({"status": "skipped", "reason": str(exc)}, indent=2))
            return 2
        print(json.dumps(to_dict(result), indent=2))
        return 0

    if args.command == "run":
        token = agent.token_status()
        if not args.dry_run and token.get("status") in {"missing", "expired"}:
            print(json.dumps({"status": "skipped", "reason": "LinkedIn token metadata is missing or expired.", "token": token}, indent=2))
            return 2
        result = agent.run(dry_run=args.dry_run)
        print(json.dumps(to_dict(result), indent=2))
        return 0 if result.status != "skipped" else 2

    if args.command == "featured-dashboard":
        token = agent.token_status()
        if not args.dry_run and token.get("status") in {"missing", "expired"}:
            print(json.dumps({"status": "skipped", "reason": "LinkedIn token metadata is missing or expired.", "token": token}, indent=2))
            return 2
        result = agent.publish_featured_dashboard(dry_run=args.dry_run)
        print(json.dumps(to_dict(result), indent=2))
        return 0 if result.status != "skipped" else 2

    if args.command == "token-status":
        print(json.dumps(agent.token_status(), indent=2))
        return 0

    if args.command == "whoami":
        print(json.dumps(LinkedInClient.from_env(config, require_owner=False).userinfo(), indent=2))
        return 0

    if args.command == "preflight":
        result = run_preflight(require_linkedin_token=args.live)
        print(json.dumps({"passed": result.passed, "checks": result.checks}, indent=2))
        return 0 if result.passed else 2

    if args.command == "show-config":
        history = PublicationHistory(config.state_dir)
        print(json.dumps({"config": public_config(config), "history_items": len(history.load())}, indent=2))
        return 0

    return 1


def print_preview(draft, visual, citations, stage_path) -> None:
    print("\n--- LINKEDIN POST PREVIEW ---\n")
    print(draft.body.strip())
    if draft.hashtags:
        print("\n" + " ".join(draft.hashtags))
    print("\n--- VISUAL ---")
    print(f"Path: {visual.path}")
    print(f"Alt text: {visual.alt_text}")
    print("\n--- SOURCES ---")
    print(f"Primary: {draft.primary_source_url}")
    for url in draft.supporting_source_urls:
        print(f"Supporting: {url}")
    if citations:
        print("\n--- GEMINI GROUNDING CITATIONS ---")
        for item in compact_citations(citations):
            print(f"- {item.get('title') or 'source'}: {item.get('url')}")
    print("\n--- APPROVAL ---")
    print(f"Exact preview staged at: {stage_path}")
    print("If the text, image, and sources all look right, publish this exact preview with:")
    print("PYTHONPATH=.vendor:src python3 -m linkedin_ai_agent.cli publish-preview --confirm")


def compact_citations(citations):
    seen = set()
    compact = []
    for item in citations:
        title = item.get("title") or "source"
        url = item.get("url") or ""
        key = (title, url)
        if key in seen:
            continue
        seen.add(key)
        compact.append(item)
        if len(compact) >= 6:
            break
    return compact


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
