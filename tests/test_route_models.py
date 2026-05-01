"""Ensure classifier model names use Ollama native format (name:tag)."""

from __future__ import annotations

from router.classifier import ROUTES

KNOWN_OLLAMA_MODELS = {
    "qwen2.5-coder:14b",
    "qwen2.5-coder:7b",
    "deepseek-coder:33b",
    "gemma4:latest",
    "phi4:latest",
    "nomic-embed-text:latest",
}


def test_classifier_models_use_ollama_format() -> None:
    """All route models must use Ollama name:tag format (colon separator)."""
    for key, r in ROUTES.items():
        assert ":" in r.model, (
            f"Route '{key}' model '{r.model}' is not in Ollama format (expected 'name:tag')"
        )


def test_classifier_models_are_known_ollama_models() -> None:
    """All route models must be in the set of known Ollama models."""
    for key, r in ROUTES.items():
        assert r.model in KNOWN_OLLAMA_MODELS, (
            f"Route '{key}' targets '{r.model}' which is not in the known Ollama model set"
        )
