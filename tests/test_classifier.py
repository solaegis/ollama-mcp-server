"""Unit tests for router.classifier — no network, no LiteLLM."""

from __future__ import annotations

import pytest
from router.classifier import ROUTES, classify, extract_text, route


def test_extract_text_user_and_system_only() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "ignored"},
    ]
    assert extract_text(messages) == "sys hello"


def test_route_returns_tuple_matching_classify() -> None:
    messages = [{"role": "user", "content": "implement a Rust trait"}]
    model, reason, key = route(messages)
    r = classify(messages)
    assert model == r.model
    assert reason == r.reason
    assert key == r.key


@pytest.mark.parametrize(
    ("content", "expected_key"),
    [
        (
            "diff --git a/foo b/foo\n+++ b/foo\n@@ -1 +1 @@\n",
            "git_commit",
        ),
        (
            "feat(api): add handler",
            "git_commit",
        ),
        (
            "implement a petgraph DAG in Rust with serde",
            "rust_code",
        ),
        (
            "compare CQRS vs event sourcing for our plugin system",
            "architecture",
        ),
        (
            "Summarize the following content.\nBe concise.\n\nContent:\nfoo",
            "summarization",
        ),
        (
            "tl;dr this patch for the team",
            "summarization",
        ),
        (
            "summarize this Rust impl block for a PR description",
            "summarization",
        ),
        (
            "write a README explaining the architecture",
            "docs_writing",
        ),
        (
            "fix the bug in this Python function",
            "general_code",
        ),
        (
            "What is photosynthesis?",
            "quick_qa",
        ),
    ],
)
def test_classify_routes(content: str, expected_key: str) -> None:
    messages = [{"role": "user", "content": content}]
    assert classify(messages).key == expected_key


def test_default_fallback() -> None:
    messages = [{"role": "user", "content": "x" * 500}]
    assert classify(messages).key == "default"


def test_routes_table_models_non_empty() -> None:
    for r in ROUTES.values():
        assert isinstance(r.model, str) and r.model
