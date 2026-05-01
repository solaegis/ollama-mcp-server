#!/usr/bin/env python3
"""Write ~/.cursor/mcp.json ollama entry and Cursor User settings for local stack."""

from __future__ import annotations

import json
import pathlib
import sys

# Cursor OpenAI override requires a non-empty API key; router ignores Bearer validation.
CURSOR_OPENAI_PLACEHOLDER_KEY = "sk-local-dev-key"
ROUTER_ORB_BASE = "http://router.ollama-stack.orb.local:4001/v1"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: setup_cursor_config.py <REPO_DIR>", file=sys.stderr)
        sys.exit(2)
    repo = pathlib.Path(sys.argv[1]).resolve()
    dist = repo / "dist" / "index.js"
    if not dist.is_file():
        print(f"error: missing {dist} — run: task build", file=sys.stderr)
        sys.exit(1)

    mcp_path = pathlib.Path.home() / ".cursor" / "mcp.json"
    mcp_path.parent.mkdir(parents=True, exist_ok=True)
    mcp = json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
    mcp.setdefault("mcpServers", {})["ollama"] = {
        "command": "node",
        "args": [str(dist)],
        "env": {
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "ROUTER_BASE_URL": "http://localhost:4001",
        },
    }
    mcp_path.write_text(json.dumps(mcp, indent=2))
    print("MCP written:", mcp_path)

    settings_path = (
        pathlib.Path.home()
        / "Library"
        / "Application Support"
        / "Cursor"
        / "User"
        / "settings.json"
    )
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings["cursor.openai.apiKey"] = CURSOR_OPENAI_PLACEHOLDER_KEY
    settings["cursor.openai.apiBase"] = ROUTER_ORB_BASE
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=4))
    print("Cursor settings written:", settings_path)
    print("Restart Cursor fully (quit app) so MCP and settings reload.")


if __name__ == "__main__":
    main()
