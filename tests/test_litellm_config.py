"""Ensure classifier target models stay aligned with config/litellm.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from router.classifier import ROUTES

REPO_ROOT = Path(__file__).resolve().parents[1]
LITELLM_PATH = REPO_ROOT / "config" / "litellm.yaml"


def test_litellm_yaml_exists() -> None:
    assert LITELLM_PATH.is_file()


def test_classifier_models_are_litellm_aliases() -> None:
    raw = yaml.safe_load(LITELLM_PATH.read_text())
    model_names = {entry["model_name"] for entry in raw["model_list"]}
    for _key, route in ROUTES.items():
        assert route.model in model_names, (
            f"Route '{route.key}' targets model_name '{route.model}' "
            f"which is missing from {LITELLM_PATH}"
        )


def test_litellm_model_list_nonempty() -> None:
    raw = yaml.safe_load(LITELLM_PATH.read_text())
    assert len(raw["model_list"]) >= 1


def test_litellm_includes_models_for_explicit_client_use() -> None:
    """deepseek-coder-v2 and phi4 are in LiteLLM but not classifier ROUTES — use by model name."""
    raw = yaml.safe_load(LITELLM_PATH.read_text())
    names = {entry["model_name"] for entry in raw["model_list"]}
    assert "deepseek-coder-v2" in names
    assert "phi4" in names
