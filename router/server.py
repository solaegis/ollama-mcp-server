"""
router/server.py — Thin FastAPI service wrapping the classifier.

Sits in front of Ollama as a pre-routing layer. Clients (Cursor, Claude,
VS Code extension) can optionally POST to /route to get a model recommendation,
or just use the /v1/chat/completions passthrough which auto-selects the model.

Requests are forwarded directly to Ollama's OpenAI-compatible API
(/v1/chat/completions).

Endpoints:
  POST /v1/chat/completions   OpenAI-compatible. Auto-routes then proxies to Ollama.
  GET  /v1/models             Synthetic OpenAI model list (used by Cursor discovery).
  POST /route                 Classification only — returns model + reason, no LLM call.
  GET  /health                Health check.
  GET  /metrics               Prometheus metrics for the router process.
  GET  /models                Router routing table (not OpenAI format).

Run:
  uvicorn router.server:app --port 4001 --reload

Or via task:
  task router-up
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

from .classifier import ROUTES, route

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Force git-commit model without classifier.
FORCE_COMMIT_MODEL_IDS = frozenset({"commit", "commit-sage", "git-commit"})

# Map OpenAI-compatible model names to Ollama native names.
# These are aliases Cursor and other OpenAI clients send when configured
# to use this router as a drop-in OpenAI provider.
OPENAI_ALIAS_MAP: dict[str, str] = {
    "gpt-4o": "qwen2.5-coder:7b",
    "gpt-4": "qwen2.5-coder:14b",
    "gpt-4o-mini": "phi4:latest",
    "gpt-3.5-turbo": "qwen2.5-coder:7b",
    "text-davinci-003": "qwen2.5-coder:7b",
}

app = FastAPI(title="Ollama Smart Router", version="1.0.0")

# Per-model chat metrics (OpenAI-compatible /v1/chat/completions through the router).
CHAT_COMPLETIONS_TOTAL = Counter(
    "router_chat_completions_total",
    "Chat completions proxied from Ollama with HTTP 200",
    labelnames=("model",),
)
CHAT_PROMPT_TOKENS_TOTAL = Counter(
    "router_chat_completion_prompt_tokens_total",
    "Prompt tokens reported in upstream usage (context / input)",
    labelnames=("model",),
)
CHAT_COMPLETION_TOKENS_TOTAL = Counter(
    "router_chat_completion_completion_tokens_total",
    "Completion tokens reported in upstream usage (output)",
    labelnames=("model",),
)

Instrumentator(
    excluded_handlers=["/health", "/metrics"],
    should_group_status_codes=False,
    should_instrument_requests_inprogress=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# ─── Health ───────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ollama": OLLAMA_URL}


# ─── Synthetic OpenAI-compatible model list ───────────────────────────────


@app.get("/v1/models")
def openai_models_list() -> JSONResponse:
    """Return a synthetic OpenAI-compatible model list.

    Cursor and other OpenAI-compatible clients call GET /v1/models to discover
    available model IDs. We build this list from ROUTES (Ollama native names),
    OPENAI_ALIAS_MAP, and router shortcuts — no outbound HTTP call needed.
    """
    seen: set[str] = set()
    model_ids: list[str] = []

    for shortcut in ("auto", "router", "commit", "commit-sage", "git-commit"):
        if shortcut not in seen:
            seen.add(shortcut)
            model_ids.append(shortcut)

    for r in ROUTES.values():
        if r.model not in seen:
            seen.add(r.model)
            model_ids.append(r.model)

    for alias in OPENAI_ALIAS_MAP:
        if alias not in seen:
            seen.add(alias)
            model_ids.append(alias)

    now = int(time.time())
    data = [
        {"id": mid, "object": "model", "created": now, "owned_by": "ollama"} for mid in model_ids
    ]
    return JSONResponse({"object": "list", "data": data})


# ─── Model map (router-specific) ───────────────────────────────────────────


@app.get("/models")
def models() -> dict:
    return {
        "routing_table": {
            name: {"model": r.model, "triggers": r.reason} for name, r in ROUTES.items()
        }
    }


# ─── Classify only ────────────────────────────────────────────────────────


@app.post("/route")
async def classify_only(request: Request) -> JSONResponse:
    """Return routing decision without making an LLM call."""
    body = await request.json()
    messages = body.get("messages", [])
    model, reason, route_key = route(messages)
    return JSONResponse({"model": model, "reason": reason, "route_key": route_key})


# ─── Main proxy ───────────────────────────────────────────────────────────


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """
    OpenAI-compatible endpoint with automatic model routing.

    If the client sends model="auto", the router picks the model.
    Models "commit", "commit-sage", "git-commit" force the git_commit model.
    OpenAI alias names (gpt-4o, gpt-3.5-turbo, etc.) are translated to Ollama
    native model names via OPENAI_ALIAS_MAP. Any other explicit model name is
    passed through unchanged.
    """
    body = await request.json()
    messages = body.get("messages", [])
    requested_model = body.get("model", "auto")

    if requested_model in FORCE_COMMIT_MODEL_IDS:
        gc = ROUTES["git_commit"]
        body["model"] = gc.model
        model = gc.model
        reason = gc.reason
        route_key = gc.key
        routed = True
    elif requested_model in ("auto", "router", ""):
        model, reason, route_key = route(messages)
        body["model"] = model
        routed = True
    else:
        translated = OPENAI_ALIAS_MAP.get(requested_model, requested_model)
        body["model"] = translated
        model = translated
        reason = "alias" if translated != requested_model else "explicit"
        route_key = "alias" if translated != requested_model else "explicit"
        routed = translated != requested_model

    # Forward to Ollama
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Routed-Model": model,
            "X-Route-Reason": reason,
            "X-Route-Key": route_key,
        },
        method="POST",
    )

    def _record_chat_metrics(
        response_body: bytes,
        status_code: int,
        media_type: str | None,
    ) -> None:
        if status_code != 200:
            return
        CHAT_COMPLETIONS_TOTAL.labels(model=model).inc()
        mtype = (media_type or "").split(";")[0].strip().lower()
        if mtype != "application/json":
            return
        try:
            parsed = json.loads(response_body.decode())
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return
        usage = parsed.get("usage")
        if not isinstance(usage, dict):
            return
        pt = usage.get("prompt_tokens")
        ctoks = usage.get("completion_tokens")
        if isinstance(pt, int) and pt >= 0:
            CHAT_PROMPT_TOKENS_TOTAL.labels(model=model).inc(pt)
        if isinstance(ctoks, int) and ctoks >= 0:
            CHAT_COMPLETION_TOKENS_TOTAL.labels(model=model).inc(ctoks)

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            content = resp.read()
            headers = dict(resp.headers)
            media_type = headers.get("Content-Type", "application/json")
            _record_chat_metrics(content, resp.status, media_type)
            # Inject routing info into response headers for observability
            if routed:
                headers["X-Routed-Model"] = model
                headers["X-Route-Reason"] = reason
                headers["X-Route-Key"] = route_key
            return Response(
                content=content,
                status_code=resp.status,
                media_type=media_type,
                headers={
                    k: v
                    for k, v in headers.items()
                    if k.lower() not in ("transfer-encoding", "connection")
                },
            )
    except urllib.error.HTTPError as e:
        return Response(content=e.read(), status_code=e.code, media_type="application/json")
    except urllib.error.URLError as e:
        return JSONResponse(
            {"error": f"Cannot reach Ollama at {OLLAMA_URL}: {e.reason}"},
            status_code=502,
        )
