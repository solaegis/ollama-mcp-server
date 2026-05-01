"""
router/classifier.py — Smart model router for the ollama-mcp-server stack.

Classifies an incoming chat request and returns the best local model for it.
Uses Ollama native model names (with colons, e.g. "qwen2.5-coder:14b") which
are passed directly to Ollama's OpenAI-compatible API at /v1/chat/completions.
Misclassification sends traffic to a suboptimal model (quality/latency); use
POST /route on the router to debug routing without invoking the LLM.

Model assignments (aligned with typical pulled sets: qwen2.5-coder, deepseek-coder, phi4, gemma4):
  git_commit     → qwen2.5-coder:14b   Diffs, conventional commits, Commit Sage
  summarization  → phi4:latest         Long-context summaries, PRs, changelogs
  rust_code      → qwen2.5-coder:14b   Strong codegen
  general_code   → qwen2.5-coder:7b    Fast, good enough for completions
  architecture   → deepseek-coder:33b  System design / tradeoffs (needs ~19GB+ headroom)
  docs_writing   → phi4:latest        Documentation and prose
  quick_qa       → gemma4:latest       Fast Q&A
  default        → qwen2.5-coder:7b    Safe fallback
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

# ─── Model routing table ──────────────────────────────────────────────────
# Models are Ollama-native names (name:tag); router forwards to Ollama /v1/chat/completions.


@dataclass(frozen=True)
class Route:
    key: str
    model: str
    reason: str


ROUTES: dict[str, Route] = {
    "git_commit": Route(
        "git_commit",
        "qwen2.5-coder:14b",
        "Git commit message, diff, or conventional commit",
    ),
    "summarization": Route(
        "summarization",
        "phi4:latest",
        "Summarization, recap, PR/changelog/standup text",
    ),
    "rust_code": Route(
        "rust_code",
        "qwen2.5-coder:14b",
        "Rust implementation task",
    ),
    "general_code": Route(
        "general_code",
        "qwen2.5-coder:7b",
        "General code task",
    ),
    "architecture": Route(
        "architecture",
        "deepseek-coder:33b",
        "Architecture/design reasoning",
    ),
    "docs_writing": Route(
        "docs_writing",
        "phi4:latest",
        "Documentation/prose writing",
    ),
    "quick_qa": Route(
        "quick_qa",
        "gemma4:latest",
        "Quick Q&A or explanation",
    ),
    "default": Route(
        "default",
        "qwen2.5-coder:7b",
        "Default fallback",
    ),
}


# ─── Keyword signals ──────────────────────────────────────────────────────
# Commit-style prompts are checked first so a Rust-heavy diff still routes to
# git_commit (commit message) rather than rust_code (implementation).
# Summarization is checked next so "summarize this Rust code" prefers long-context
# phi4 over rust_code.

COMMIT_SIGNALS = re.compile(
    r"(diff\s+--git|git\s+diff\b|^\s*@@\s|^\+\+\+\s+[ab]/|^---\s+[ab]/|^\s*index\s+[0-9a-f]{7,}\b|"
    r"\bconventional\s+commit\b|\bcommit\s+message\b|\bstaged\s+changes\b|"
    r"\b(feat|fix|chore|refactor|docs|test|perf|style|ci)\([^)]*\)\s*:\s*|"
    r"\bgenerate\s+(a\s+)?commit\b|\bwrite\s+(a\s+)?commit\b|"
    r"\bsuggest\s+(a\s+)?commit\b)",
    re.IGNORECASE | re.MULTILINE,
)

SUMMARIZE_SIGNALS = re.compile(
    r"\b(summarize\s+(the\s+)?(following|this|below)|\bsummary\b|tl;dr|tldr|"
    r"high.level\s+overview|executive\s+summary|recap\b|"
    r"pr\s+description|changelog\s+entry|standup\s+update|release\s+notes|"
    r"summarize\s+for)\b",
    re.IGNORECASE,
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
    if SUMMARIZE_SIGNALS.search(text):
        return ROUTES["summarization"]
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
    """Return (ollama_model_name, human_reason, route_key)."""
    r = classify(messages)
    return r.model, r.reason, r.key
