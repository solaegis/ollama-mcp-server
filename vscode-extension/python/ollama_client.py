"""
ollama_client.py — Python backend for the VS Code extension.

Runs as a subprocess launched by the TypeScript extension.
Communicates via stdin/stdout using newline-delimited JSON (one request,
one response per line).

Protocol:
  stdin:  {"id": 1, "method": "chat", "params": {...}}
  stdout: {"id": 1, "result": "...", "error": null}
"""

from __future__ import annotations

import json
import sys
import os
import urllib.request
import urllib.error
from typing import Any

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
LITELLM_BASE = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-local-dev-key")


# ─── HTTP helpers ──────────────────────────────────────────────────────────

def _post(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed to {url}: {e.reason}")


def _get(url: str) -> dict:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed to {url}: {e.reason}")


# ─── Ollama methods ────────────────────────────────────────────────────────

def list_models() -> list[dict]:
    """Return list of locally available models."""
    data = _get(f"{OLLAMA_BASE}/api/tags")
    return [
        {
            "name": m["name"],
            "size_gb": round(m["size"] / 1e9, 1),
            "params": m.get("details", {}).get("parameter_size", "?"),
        }
        for m in data.get("models", [])
    ]


def loaded_models() -> list[dict]:
    """Return models currently loaded in memory."""
    data = _get(f"{OLLAMA_BASE}/api/ps")
    return [
        {
            "name": m["name"],
            "vram_gb": round(m.get("size_vram", 0) / 1e9, 1),
        }
        for m in data.get("models", [])
    ]


def chat(model: str, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Send chat to Ollama directly (bypasses LiteLLM)."""
    resp = _post(
        f"{OLLAMA_BASE}/api/chat",
        {"model": model, "messages": messages, "stream": False,
         "options": {"temperature": temperature, "num_predict": max_tokens}},
    )
    return resp["message"]["content"]


def chat_litellm(model: str, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Send chat via LiteLLM proxy (OpenAI-compatible)."""
    resp = _post(
        f"{LITELLM_BASE}/v1/chat/completions",
        {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
    )
    return resp["choices"][0]["message"]["content"]


def pull_model(model: str) -> str:
    """Pull a model from the Ollama registry."""
    resp = _post(f"{OLLAMA_BASE}/api/pull", {"name": model, "stream": False})
    return resp.get("status", "unknown")


def health() -> dict:
    """Check which services are reachable."""
    results: dict[str, bool] = {}
    for name, url in [("ollama", f"{OLLAMA_BASE}/api/tags"), ("litellm", f"{LITELLM_BASE}/health/liveliness")]:
        try:
            _get(url)
            results[name] = True
        except Exception:
            results[name] = False
    return results


# ─── Dispatch ─────────────────────────────────────────────────────────────
# Each entry is (fn, takes_params). No-arg functions get called with no
# arguments regardless of what params dict arrives from the caller.

METHODS: dict[str, tuple[Any, bool]] = {
    "list_models":   (list_models,   False),
    "loaded_models": (loaded_models, False),
    "health":        (health,        False),
    "chat":          (lambda p: chat(p["model"], p["messages"], p.get("temperature", 0.7), p.get("max_tokens", 4096)), True),
    "chat_litellm":  (lambda p: chat_litellm(p["model"], p["messages"], p.get("temperature", 0.7), p.get("max_tokens", 4096)), True),
    "pull_model":    (lambda p: pull_model(p["model"]), True),
}


def handle(line: str) -> str:
    try:
        req = json.loads(line)
        req_id = req.get("id", 0)
        method = req.get("method", "")
        params = req.get("params", {})

        entry = METHODS.get(method)
        if entry is None:
            return json.dumps({"id": req_id, "result": None, "error": f"Unknown method: {method}"})

        fn, takes_params = entry
        result = fn(params) if takes_params else fn()
        return json.dumps({"id": req_id, "result": result, "error": None})

    except Exception as exc:
        req_id = 0
        try:
            req_id = json.loads(line).get("id", 0)
        except Exception:
            pass
        return json.dumps({"id": req_id, "result": None, "error": str(exc)})


def main() -> None:
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle(line)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
