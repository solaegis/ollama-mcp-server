#!/usr/bin/env python3
"""
Generate a reference list of LiteLLM model_name aliases from config/litellm.yaml.

Why not write Cursor User settings.json?
  Cursor does not reliably read ad-hoc keys like "cursor.openai.models" for the
  Settings UI. It discovers models by calling OpenAI-compatible GET /v1/models
  on your API base URL. The smart router now proxies GET /v1/models to LiteLLM,
  so with API Base set to http://localhost:4001/v1 (or your OrbStack router URL),
  use "Verify" / model refresh in Cursor — the dropdown should populate from LiteLLM.

This script still writes ~/.cursor/ollama-router-model-list.json for quick reference
and prints the same list.

Run from repo root: uv run python scripts/sync_cursor_models.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROUTER_EXTRAS = ("auto", "router", "commit", "commit-sage")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def litellm_path() -> Path:
    return repo_root() / "config" / "litellm.yaml"


def model_names_from_config(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text())
    names = [entry["model_name"] for entry in data["model_list"]]
    seen: set[str] = set()
    ordered: list[str] = []
    for n in (*ROUTER_EXTRAS, *names):
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def try_fetch_openai_models(router_base: str, api_key: str) -> dict | None:
    """GET {router_base}/v1/models — router_base should end with /v1 or be origin only."""
    base = router_base.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/models"
    else:
        url = f"{base}/v1/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def main() -> None:
    cfg = litellm_path()
    if not cfg.is_file():
        print(f"ERROR: {cfg} not found (run from repo root)", file=sys.stderr)
        sys.exit(1)

    models = model_names_from_config(cfg)

    cursor_dir = Path.home() / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    backup = cursor_dir / "ollama-router-model-list.json"
    payload = {
        "models": models,
        "note": (
            "LiteLLM aliases + router shortcuts. Cursor calls GET /v1/models on your API base; "
            "the router proxies that to LiteLLM."
        ),
    }
    backup.write_text(json.dumps(payload, indent=2) + "\n")
    print("Wrote", backup)

    router_url = os.environ.get("ROUTER_OPENAI_BASE", "http://localhost:4001/v1")
    api_key = os.environ.get("LITELLM_MASTER_KEY", "sk-local-dev-key")
    live = try_fetch_openai_models(router_url, api_key)
    if live is not None:
        ids = [d.get("id", "") for d in live.get("data", []) if isinstance(d, dict)]
        url_display = f"{router_url.rstrip('/')}/models"
        print(f"OK: GET {url_display} returned {len(ids)} model id(s) from the router.")
        if ids:
            print("  First few:", ", ".join(ids[:8]) + ("…" if len(ids) > 8 else ""))
    else:
        print(
            f"Note: Could not reach router at {router_url} (stack down or wrong URL).\n"
            "After `task up`, set API Base to the router and use Verify in Cursor."
        )

    print()
    print("Cursor: Settings → Models → OpenAI → Override base URL →", router_url)
    print("        API key:", api_key, "(or your LITELLM_MASTER_KEY)")
    print(
        "        Click Verify. Models come from GET /v1/models, not from settings.json."
    )


if __name__ == "__main__":
    main()
