"""HTTP tests for router.server (FastAPI) with LiteLLM mocked."""

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
    assert "litellm" in body


def test_models_lists_routes() -> None:
    r = client.get("/models")
    assert r.status_code == 200
    data = r.json()
    assert "routing_table" in data
    assert "git_commit" in data["routing_table"]


@patch("router.server.urllib.request.urlopen")
def test_v1_models_proxies_to_litellm(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _mock_urlopen_response(
        {"object": "list", "data": [{"id": "qwen2.5-coder-7b", "object": "model"}]}
    )
    r = client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "qwen2.5-coder-7b"
    mock_urlopen.assert_called_once()
    call_args = mock_urlopen.call_args[0][0]
    assert "/v1/models" in getattr(call_args, "full_url", str(call_args))


def test_route_endpoint() -> None:
    r = client.post(
        "/route",
        json={"messages": [{"role": "user", "content": "diff --git a/x b/x"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "qwen2.5-coder-14b"
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
def test_chat_completions_auto_forwards_to_litellm(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _mock_urlopen_response(
        {
            "id": "chatcmpl-test",
            "model": "qwen2.5-coder-7b",
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"},
            ],
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


@patch("router.server.urllib.request.urlopen")
def test_chat_completions_litellm_unreachable(mock_urlopen: MagicMock) -> None:
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("refused")
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 502
    assert "LiteLLM" in r.json()["error"]


@patch("router.server.urllib.request.urlopen")
def test_chat_completions_http_error(mock_urlopen: MagicMock) -> None:
    import urllib.error

    err = urllib.error.HTTPError(
        "http://localhost:4000/v1/chat/completions",
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
