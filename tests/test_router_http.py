"""HTTP tests for router.server (FastAPI) with Ollama upstream mocked."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from router.server import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "ollama" in body


def test_metrics_prometheus_format() -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
    assert r.headers.get("content-type", "").startswith("text/plain")


def test_models_lists_routes() -> None:
    r = client.get("/models")
    assert r.status_code == 200
    data = r.json()
    assert "routing_table" in data
    assert "git_commit" in data["routing_table"]


def test_v1_models_returns_synthetic_list() -> None:
    r = client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    assert len(body["data"]) > 0
    ids = {m["id"] for m in body["data"]}
    assert "auto" in ids
    assert "qwen2.5-coder:14b" in ids


def test_route_endpoint() -> None:
    r = client.post(
        "/route",
        json={"messages": [{"role": "user", "content": "diff --git a/x b/x"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "qwen2.5-coder:14b"
    assert body["route_key"] == "git_commit"


def _mock_urlopen_response(payload: dict, status: int = 200) -> MagicMock:
    body = json.dumps(payload).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.status = status
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp
    mock_cm.__exit__.return_value = None
    return mock_cm


@patch("router.server.urllib.request.urlopen")
def test_chat_completions_auto_forwards_to_ollama(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _mock_urlopen_response(
        {
            "id": "chatcmpl-test",
            "model": "qwen2.5-coder-7b",
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"},
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "auto",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert r.status_code == 200
    mock_urlopen.assert_called_once()
    call_args = mock_urlopen.call_args[0][0]
    assert "/v1/chat/completions" in getattr(call_args, "full_url", str(call_args))
    sent = json.loads(call_args.data.decode())
    assert sent["model"] != "auto"

    m = client.get("/metrics")
    assert m.status_code == 200
    text = m.text
    assert "router_chat_completions_total{" in text
    assert "router_chat_completion_prompt_tokens_total{" in text
    assert "router_chat_completion_completion_tokens_total{" in text


@patch("router.server.urllib.request.urlopen")
def test_chat_completions_ollama_unreachable(mock_urlopen: MagicMock) -> None:
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("refused")
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 502
    assert "Ollama" in r.json()["error"]


@patch("router.server.urllib.request.urlopen")
def test_chat_completions_http_error(mock_urlopen: MagicMock) -> None:
    import urllib.error

    err = urllib.error.HTTPError(
        "http://localhost:11434/v1/chat/completions",
        500,
        "Internal Server Error",
        {},
        BytesIO(b'{"error":"boom"}'),
    )
    mock_urlopen.side_effect = err
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 500
