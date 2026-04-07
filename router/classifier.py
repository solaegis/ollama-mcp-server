"""
router/classifier.py — Smart model router for the ollama-mcp-server stack.

Classifies an incoming chat request and returns the best local model for it.
Uses the LiteLLM alias names from config/litellm.yaml (no colons — colons
are YAML special characters and cause parse failures in model_name fields).

Model assignments (tuned for Nuvent / Rust / IaC workloads):
  git_commit     → qwen2.5-coder-14b   Diffs, conventional commits, Commit Sage
  rust_code      → qwen2.5-coder-14b   Best Rust on Polyglot benchmark
  general_code   → qwen2.5-coder-7b    Fast, good enough for completions
  architecture   → gemma4-27b           256K context, strong reasoning
  docs_writing   → llama3.3-70b         Best local prose generation
  quick_qa       → gemma4               Fast, 128K context
  default        → qwen2.5-coder-7b    Safe fallback
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


# ─── Model routing table ──────────────────────────────────────────────────
# Names must match model_name entries in config/litellm.yaml exactly.

@dataclass(frozen=True)
class Route:
    key: str
    model: str
    reason: str


ROUTES: dict[str, Route] = {
    "git_commit": Route(
        "git_commit",
        "qwen2.5-coder-14b",
        "Git commit message, diff, or conventional commit",
    ),
    "rust_code": Route(
        "rust_code",
        "qwen2.5-coder-14b",
        "Rust implementation task",
    ),
    "general_code": Route(
        "general_code",
        "qwen2.5-coder-7b",
        "General code task",
    ),
    "architecture": Route(
        "architecture",
        "gemma4-27b",
        "Architecture/design reasoning",
    ),
    "docs_writing": Route(
        "docs_writing",
        "llama3.3-70b",
        "Documentation/prose writing",
    ),
    "quick_qa": Route(
        "quick_qa",
        "gemma4",
        "Quick Q&A or explanation",
    ),
    "default": Route(
        "default",
        "qwen2.5-coder-7b",
        "Default fallback",
    ),
}


# ─── Keyword signals ──────────────────────────────────────────────────────
# Commit-style prompts are checked first so a Rust-heavy diff still routes to
# git_commit (commit message) rather than rust_code (implementation).

COMMIT_SIGNALS = re.compile(
    r"(diff\s+--git|git\s+diff\b|^\s*@@\s|^\+\+\+\s+[ab]/|^---\s+[ab]/|^\s*index\s+[0-9a-f]{7,}\b|"
    r"\bconventional\s+commit\b|\bcommit\s+message\b|\bstaged\s+changes\b|"
    r"\b(feat|fix|chore|refactor|docs|test|perf|style|ci)\([^)]*\)\s*:\s*|"
    r"\bgenerate\s+(a\s+)?commit\b|\bwrite\s+(a\s+)?commit\b|"
    r"\bsuggest\s+(a\s+)?commit\b)",
    re.IGNORECASE | re.MULTILINE,
)

RUST_SIGNALS = re.compile(
    r"\b(rust|cargo|tokio|async|await|trait|impl|lifetime|borrow|ownership|"
    r"clippy|wasm|wit|wasmtime|wasmparser|petgraph|serde|thiserror|anyhow|"
    r"sqlx|postgres|ledger|event.sourc|nuvent|reconcil|dag|crate|mod\s+\w+|"
    r"pub\s+(fn|struct|enum|trait)|#\[derive|Result<|Option<|Vec<|HashMap<|"
    r"\.unwrap\(\)|\.expect\(|match\s+\w+\s*\{)\b",
    re.IGNORECASE,
)

ARCH_SIGNALS = re.compile(
    r"\b(architect|design\s+pattern|system\s+design|how\s+should\s+i\s+(structure|design|build)|"
    r"trade.?off|scalab|event.sourc|cqrs|ddd|domain.driven|iac\s+engine|"
    r"wasm\s+(plugin|sandbox|interface)|wit\s+(interface|type|world)|"
    r"plugin\s+system|provider\s+pattern|compare\s+approach|which\s+(approach|pattern|design))\b",
    re.IGNORECASE,
)

DOCS_SIGNALS = re.compile(
    r"\b(write\s+(a\s+)?(doc|readme|patent|memo|spec|proposal|changelog|blog|explanation)|"
    r"document\s+(this|the|my)|explain\s+(in\s+(detail|depth|plain)|to\s+(a\s+)?non)|"
    r"summarize\s+for|draft\s+(a\s+)?(letter|email|memo|patent|proposal)|"
    r"rewrite\s+(this|the)\s+(paragraph|section|doc)|improve\s+(the\s+)?(writing|prose|clarity))\b",
    re.IGNORECASE,
)

CODE_SIGNALS = re.compile(
    r"\b(function|class|method|variable|algorithm|implement|debug|fix\s+(this|the)\s+(code|bug)|"
    r"refactor|test|typescript|javascript|python|sql|yaml|json|bash|shell\s+script|"
    r"write\s+(a\s+)?(function|class|test|script|query))\b",
    re.IGNORECASE,
)

QA_SIGNALS = re.compile(
    r"^.{0,200}(\?|what\s+is|what\s+does|how\s+does|why\s+(does|is|are|do)|"
    r"can\s+you\s+explain|tell\s+me\s+(about|what)|list\s+(the|all)|"
    r"what\s+are\s+the\s+(best|main|key)|give\s+me\s+(a\s+)?(quick|brief|short)).{0,200}$",
    re.IGNORECASE,
)


# ─── Classifier ───────────────────────────────────────────────────────────

def extract_text(messages: Sequence[dict]) -> str:
    parts = []
    for m in messages:
        if m.get("role") in ("user", "system") and isinstance(m.get("content"), str):
            parts.append(m["content"])
    return " ".join(parts)


def classify(messages: Sequence[dict]) -> Route:
    text = extract_text(messages)

    if COMMIT_SIGNALS.search(text):
        return ROUTES["git_commit"]
    if RUST_SIGNALS.search(text):
        return ROUTES["rust_code"]
    if ARCH_SIGNALS.search(text):
        return ROUTES["architecture"]
    if DOCS_SIGNALS.search(text):
        return ROUTES["docs_writing"]
    if CODE_SIGNALS.search(text):
        return ROUTES["general_code"]
    if QA_SIGNALS.search(text):
        return ROUTES["quick_qa"]
    return ROUTES["default"]


def route(messages: Sequence[dict]) -> tuple[str, str, str]:
    """Return (lite_llm_model_name, human_reason, route_key)."""
    r = classify(messages)
    return r.model, r.reason, r.key
