"""
router/server.py — Thin FastAPI service wrapping the classifier.

Sits in front of LiteLLM as a pre-routing layer. Clients (Cursor, Claude,
VS Code extension) can optionally POST to /route to get a model recommendation,
or just use the /v1/chat/completions passthrough which auto-selects the model.

Endpoints:
  POST /v1/chat/completions   OpenAI-compatible. Auto-routes then proxies to LiteLLM.
  GET  /v1/models             OpenAI model list (proxied from LiteLLM; used by Cursor discovery).
  POST /route                 Classification only — returns model + reason, no LLM call.
  GET  /health                Health check.
  GET  /models                Router routing table (not OpenAI format).

Run:
  uvicorn router.server:app --port 4001 --reload

Or via task:
  task router-up
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .classifier import ROUTES, route

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-local-dev-key")

# Force git-commit model (LiteLLM model_name) without classifier.
FORCE_COMMIT_MODEL_IDS = frozenset({"commit", "commit-sage", "git-commit"})

app = FastAPI(title="Ollama Smart Router", version="1.0.0")


# ─── Health ───────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "litellm": LITELLM_URL}


# ─── OpenAI-compatible model list (for Cursor / clients that call GET /v1/models) ─


@app.get("/v1/models")
def openai_models_list() -> Response:
    """Proxy LiteLLM's /v1/models so clients using this base URL can discover model IDs."""
    req = urllib.request.Request(
        f"{LITELLM_URL}/v1/models",
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            headers = dict(resp.headers)
            return Response(
                content=content,
                status_code=resp.status,
                media_type=headers.get("Content-Type", "application/json"),
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
            {"error": f"Cannot reach LiteLLM at {LITELLM_URL}: {e.reason}"},
            status_code=502,
        )


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
    Model "gpt-3.5-turbo" uses the classifier when the route is git_commit
    (Commit Sage default); otherwise passes through to LiteLLM alias.
    Any other explicit model name is passed through unchanged.
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
    elif requested_model == "gpt-3.5-turbo":
        model_c, reason_c, route_key_c = route(messages)
        if route_key_c == "git_commit":
            body["model"] = model_c
            model = model_c
            reason = reason_c
            route_key = route_key_c
            routed = True
        else:
            model = requested_model
            reason = "explicit"
            route_key = "passthrough"
            routed = False
    else:
        model = requested_model
        reason = "explicit"
        route_key = "explicit"
        routed = False

    # Forward to LiteLLM
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{LITELLM_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_KEY}",
            "X-Routed-Model": model,
            "X-Route-Reason": reason,
            "X-Route-Key": route_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            content = resp.read()
            headers = dict(resp.headers)
            # Inject routing info into response headers for observability
            if routed:
                headers["X-Routed-Model"] = model
                headers["X-Route-Reason"] = reason
                headers["X-Route-Key"] = route_key
            return Response(
                content=content,
                status_code=resp.status,
                media_type=headers.get("Content-Type", "application/json"),
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
            {"error": f"Cannot reach LiteLLM at {LITELLM_URL}: {e.reason}"},
            status_code=502,
        )
