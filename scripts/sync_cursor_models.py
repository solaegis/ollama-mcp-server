#!/usr/bin/env python3
"""
Write ~/.cursor/ollama-router-model-list.json from the smart router's GET /v1/models.

Cursor discovers models by calling OpenAI-compatible GET /v1/models on your API base
(router on port 4001). This script mirrors that list for offline reference.

Run from repo root: uv run python scripts/sync_cursor_models.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def try_fetch_openai_models(router_base: str, bearer: str) -> dict | None:
    """GET {router_base}/v1/models — router_base should end with /v1 or be origin only."""
    base = router_base.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/models"
    else:
        url = f"{base}/v1/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {bearer}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def main() -> None:
    router_url = os.environ.get("ROUTER_OPENAI_BASE", "http://localhost:4001/v1")
    bearer = os.environ.get("ROUTER_BEARER_TOKEN", "sk-local-dev-key")
    live = try_fetch_openai_models(router_url, bearer)
    if live is None:
        print(
            f"ERROR: could not GET models from {router_url} (stack down? run: task up)",
            file=sys.stderr,
        )
        sys.exit(1)

    ids = [d.get("id", "") for d in live.get("data", []) if isinstance(d, dict) and d.get("id")]
    cursor_dir = Path.home() / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    backup = cursor_dir / "ollama-router-model-list.json"
    payload = {
        "models": ids,
        "note": "From GET /v1/models on the smart router. Cursor uses the same endpoint when you click Verify.",
    }
    backup.write_text(json.dumps(payload, indent=2) + "\n")
    print("Wrote", backup)
    print(f"OK: {len(ids)} model id(s) from router.")
    if ids:
        print("  First few:", ", ".join(ids[:12]) + ("…" if len(ids) > 12 else ""))

    print()
    print("Cursor: Settings → Models → OpenAI → Override base URL →", router_url)
    print("        API key:", bearer, "(placeholder; router does not validate)")
    print("        Click Verify. Models come from GET /v1/models.")


if __name__ == "__main__":
    main()
