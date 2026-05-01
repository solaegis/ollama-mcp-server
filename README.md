# ollama-mcp-server

Local LLM stack for Mac — Ollama runtime, OpenAI-compatible proxy, MCP server for Claude/Cursor/Antigravity, and a VS Code extension with model picker and selection tools.

## What's included

| Component | Purpose |
|---|---|
| **MCP server** (`src/`) | Exposes Ollama tools to any MCP client: list, generate, chat, embeddings |
| **Docker stack** (`docker/`) | Smart router + Open WebUI + Prometheus + Grafana; **default** uses **native** Ollama on the host (Metal). Optional **Linux Ollama** container via `task up-container-ollama`. |
| **VS Code extension** (`vscode-extension/`) | Status bar, model picker, send/rewrite selection, chat panel |
| **Taskfile** | One-command lifecycle for all of the above |

---

## Prerequisites

Install once via Homebrew:

```bash
# OrbStack — Docker runtime for Mac (faster than Docker Desktop)
brew install orbstack

# Task runner
brew install go-task

# Node.js (for MCP server + extension build)
brew install node

# Python 3 (already on macOS, but ensure it's on PATH)
python3 --version   # should be 3.10+

# Ollama (native on macOS — Metal). Default `task up` uses this; containers reach it via host.docker.internal.
brew install ollama
# or install from https://ollama.com/download and keep the app running
```


## Quick start

```bash
cd ~/git/solaegis/ollama-mcp-server

# 1. Build the MCP server
task build

# 2. Copy and edit environment (change keys, adjust default models)
cp .env.example .env

# 3. Start native Ollama on the host (menu bar app or `ollama serve`), then start the Docker stack
#    (router, Web UI, metrics — pulls default models into native Ollama on first run)
task up

# 4. Verify everything
task test-ollama      # lists available models
task orb-check        # optional: verify OrbStack hostnames for Cursor

# 5. Wire MCP into Cursor (writes ~/.cursor/mcp.json)
task setup-cursor

# 6. Wire MCP into Claude Desktop
task setup-claude-desktop
```

### Service endpoints after `task up`

Default stack: **Ollama runs on the Mac host** (`localhost:11434`, Metal). Compose services use `host.docker.internal:11434` to reach it. For a **Linux Ollama container** instead (CPU in a VM on Mac), use **`task up-container-ollama`** and stop native Ollama to avoid port **11434** conflicts.

| Service | URL | Purpose |
|---|---|---|
| Ollama API | `http://localhost:11434` | Native Ollama on host (default) |
| Smart router | `http://localhost:4001` | OpenAI-compatible + classifier → Ollama; **use this for Cursor / Commit Sage** |
| Open WebUI | `http://localhost:8080` | Browser chat UI |
| Grafana | `http://localhost:3001` | Usage metrics |
| Prometheus | `http://localhost:9090` | Raw metrics |

---

## Choosing an agent (or provider)

Cursor and other clients can use **several** “agents” or backends at once. Use this as a rule of thumb:

| Use this | When |
|---|---|
| **Cursor cloud / subscription models** (default Chat, Composer, etc.) | Hard problems: architecture, large refactors, debugging across many files, planning, or when you need the strongest available model. |
| **MCP tools** (`ollama_task`, `ollama_summarize`, `ollama_git`, …) | Offload **repetitive or token-heavy** work to **local** models: conventional commits from diffs, long summaries, embeddings, quick local checks. Saves **context and cost** on the cloud agent; the **smart router** picks a model from prompt content when the tool uses `model: auto`. Prefer these tools in the **agent** chat when the task does not need frontier reasoning. |
| **OpenAI-compatible override → smart router** (`http://localhost:4001/v1`, model `auto` or an Ollama model id) | **Local** Chat sessions that follow the same **routing** as MCP (code vs docs vs summarization, etc.). Use **Verify** so `GET /v1/models` populates the list. Not every Composer surface respects custom providers—if in doubt, use **Chat** or **MCP** for local routing. |
| **VS Code / Cursor extension** (`Ollama: …` commands) | **Editor-native** flows: send selection, rewrite selection, side chat panel, model picker. Calls **Ollama directly** by default; optional **router** URL in settings for OpenAI-style calls via the smart router. |

**Practical split:** keep **cloud** for the work only a strong model should do; push **commits, summaries, and bulk local inference** to MCP or the local router so your main agent’s context stays focused on coding and design.

---

## Model management

```bash
task list                          # list pulled models
task pull -- qwen2.5-coder:14b    # pull a model
task ps                            # show models loaded in memory
task rm-model -- phi4:latest       # delete a model
```

Browse available models: https://ollama.com/library

### Recommended models (M2 Ultra — 192GB unified memory)

| Model | Use case | VRAM |
|---|---|---|
| `qwen2.5-coder:7b` | Code completion, default | ~5 GB |
| `qwen2.5-coder:14b` | Code + reasoning | ~10 GB |
| `deepseek-coder:6.7b` | DeepSeek Coder; fits typical Docker Desktop RAM for `ollama` | ~4 GB |
| `deepseek-coder:33b` | DeepSeek Coder; strong codegen (see Docker note below) | ~19 GB |
| `phi4:latest` | General, summarization, docs routing | ~9 GB |
| `gemma4:latest` | Quick Q&A routing | ~10 GB |
| `nomic-embed-text` | Embeddings | ~300 MB |

Several of these can be loaded simultaneously on the M2 Ultra when Ollama has access to the full machine (native install or a container with a high memory limit).

#### DeepSeek Coder (library tags)

Official sizes on [ollama.com/library/deepseek-coder](https://ollama.com/library/deepseek-coder): `deepseek-coder` / `:1.3b`, `:6.7b`, `:33b` (16K context).

#### Docker Ollama on Apple Silicon vs native (Metal)

**Default (`task up`):** inference uses **native Ollama** on the host; the compose **`ollama` service is off**. Router, Open WebUI, model-puller, and Prometheus reach the host via **`host.docker.internal:11434`** (see [docker/compose.hybrid-host.yaml](docker/compose.hybrid-host.yaml)).

**Opt-in (`task up-container-ollama`):** the **`ollama`** service in [docker/compose.yaml](docker/compose.yaml) runs the **Linux** `ollama/ollama` image. On a Mac VM that is typically **CPU** inference (`GPULayers: []`, `CPU model buffer` in logs), not Metal. Do **not** run this alongside native Ollama on the same **11434** port.

- **`deepseek-coder:33b`** often **fails to load** if the Docker VM / container cap is around **~16 GiB** (weights alone are on the order of ~18 GB on disk; the runner needs additional headroom). Raise **OrbStack / Docker Desktop → memory**, or stay on **native** Ollama for large models.
- **`deepseek-coder:6.7b`** is a practical choice when the VM memory cap is tight.

**Sample throughput (CPU inference in Docker container, 2026-05-01):** same prompts, `num_predict=280`, `temperature=0.2`, host `localhost:11434` → `ollama` container (not the default hybrid path).

| Model | Task | Output tokens (eval) | Wall (s) | eval tok/s (approx.) |
|---|---|---:|---:|---:|
| `qwen2.5-coder:14b` | Python `chunked` | 80 | 24.9 | 4.9 |
| `qwen2.5-coder:14b` | Rust `Arc<Mutex<u64>>` counter | 134 | 29.3 | 4.8 |
| `deepseek-coder:6.7b` | Python `chunked` | 254 | 33.7 | 8.9 |
| `deepseek-coder:6.7b` | Rust `Arc<Mutex<u64>>` counter | 240 | 37.8 | 6.5 |

*(DeepSeek hit the output cap more often in this run, so token counts are not identical; use the script pattern in `task` / `curl` / small Python client to reproduce on your machine.)*

---

## IDE integration

### Cursor

`task setup-cursor` writes the MCP config automatically. Optional: `OLLAMA_MCP_USE_ORB_DNS=1 task setup-cursor` sets MCP **`ROUTER_BASE_URL`** to `http://router.ollama-stack.orb.local:4001` (same hostname family as the OpenAI override). To do it manually:

`~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["/Users/lvavasour/git/solaegis/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "ROUTER_BASE_URL": "http://localhost:4001"
      }
    }
  }
}
```

For the **OpenAI-compatible provider** (Cursor chat/composer using local models), point at the **smart router** (port **4001**) so requests can be classified (code vs docs vs **git commit**, etc.):

Cursor Settings → Models → OpenAI override (or `cursor.openai.apiBase` / `cursor.openai.apiKey` in `settings.json`):
- API Base: `http://localhost:4001/v1` (or `http://router.ollama-stack.orb.local:4001/v1` from `task setup-cursor` / `task status` — OrbStack DNS for the `router` service; avoids Cursor SSRF blocks on localhost). The router serves **`GET /v1/models`** from its routing table so Cursor can **discover** model IDs (use **Verify** if the list is empty).
- API Key: any non-empty string (e.g. `sk-local-dev-key`) — placeholder Bearer token; the router does not validate it.
- Model: `auto` or `router` for automatic routing; or `commit` / `commit-sage` to force the git-commit model; or any Ollama model id the router exposes (e.g. `qwen2.5-coder:7b`) for a fixed model.
- `task sync-cursor-models` writes `~/.cursor/ollama-router-model-list.json` from live `GET /v1/models`; it does **not** populate Cursor’s Settings UI (Cursor reads models from the API, not arbitrary `settings.json` keys).

**Commit Sage** (VS Code / Cursor extension `VizzleTF.geminicommit`): set provider to **OpenAI**, **Base URL** `http://localhost:4001/v1`, API key as above, and keep default model **`gpt-3.5-turbo`** — the router upgrades to **`qwen2.5-coder-14b`** when the prompt looks like a diff/commit. To force the commit model without classification, set model to **`commit`** or **`commit-sage`**.

### Windsurf

Settings → AI Providers → Add Custom:
- Base URL: `http://localhost:4001/v1`
- API Key: `sk-local-dev-key` (placeholder)

### Zed

`~/.config/zed/settings.json`:
```json
{
  "language_models": {
    "openai": {
      "api_url": "http://localhost:4001/v1",
      "available_models": [
        { "name": "qwen2.5-coder:7b", "max_tokens": 32768 },
        { "name": "phi4", "max_tokens": 16384 }
      ]
    }
  }
}
```

### Antigravity

Settings → MCP Servers → Add:
- Command: `node`
- Args: `/Users/lvavasour/git/solaegis/ollama-mcp-server/dist/index.js`
- Env: `OLLAMA_BASE_URL=http://localhost:11434`, `ROUTER_BASE_URL=http://localhost:4001`

### Claude Desktop

`task setup-claude-desktop` writes the config automatically.

---

## VS Code / Cursor extension

The extension gives you a status bar indicator, model picker, selection tools, and an inline chat panel — all backed by the Python client talking directly to Ollama.

### Install

```bash
# Build the extension
task ext-install

# Package as .vsix
task ext-package

# Install in Cursor / VS Code
code --install-extension vscode-extension/ollama-local-llm-1.0.0.vsix
# or open Cursor → Extensions → "Install from VSIX"
```

### Commands

| Command | Shortcut | Description |
|---|---|---|
| `Ollama: Switch Model` | click status bar | QuickPick from available models |
| `Ollama: Send Selection to LLM` | `⌘⇧O` | Send selected code + custom instruction |
| `Ollama: Rewrite / Improve Selection` | `⌘⇧R` | Rewrite selected code; shows diff or replaces |
| `Ollama: Open Chat Panel` | palette | Persistent chat panel beside editor |
| `Ollama: Pull New Model` | palette | Pull a model by name |

### Settings

| Setting | Default | Description |
|---|---|---|
| `ollama.baseUrl` | `http://localhost:11434` | Ollama API URL |
| `ollama.routerUrl` | `http://localhost:4001` | Smart router base URL (OpenAI-compatible `/v1`) |
| `ollama.routerBearerToken` | `sk-local-dev-key` | Bearer sent to router (placeholder) |
| `ollama.defaultModel` | `qwen2.5-coder:7b` | Active model |
| `ollama.temperature` | `0.7` | Sampling temperature |

### Status bar indicators

```
● qwen2.5-coder:7b +router  — model loaded in memory, smart router reachable
○ qwen2.5-coder:7b          — model available but not yet loaded
✕ qwen2.5-coder:7b          — Ollama unreachable
```

---

## MCP tools reference

Once wired into Cursor/Claude Desktop, these tools are available to the AI agent:

| Tool | Description |
|---|---|
| `ollama_task` | General local task; router picks model (`model: auto`). |
| `ollama_git` | Git / GitHub: conventional commit (default `git_task`), PR title/body, numbered `git`+`gh` plans, review-thread replies. Does not run shell—paste output of `git diff` / `gh pr diff` where needed. |
| `ollama_summarize` | Long-context summaries (PR text, changelogs, etc.). |
| `ollama_list_models` | List all pulled models |
| `ollama_generate` | Single-turn prompt → response |
| `ollama_chat` | Multi-turn conversation with message history |
| `ollama_embeddings` | Generate vector embeddings |

Example usage in Cursor Agent:

```
Use ollama_git with git_task pr_body; paste the output of gh pr diff into diff.
Use ollama_chat with qwen2.5-coder:7b to rewrite this prompt to be more specific
```

---

## Changing router models

Edit [`router/classifier.py`](router/classifier.py) (`ROUTES` and routing logic), then restart the router: `task restart -- router`.

---

## All task commands

```bash
task build              # install npm deps + compile MCP server TypeScript
task inspect            # launch MCP Inspector (browser UI for testing tools)
task up                       # start stack (native Ollama on host :11434)
task up-container-ollama      # optional: Linux Ollama in Docker instead (stop native first)
task down                     # stop default stack
task down-container-ollama    # stop stack started with up-container-ollama
task update                   # pull router, Web UI, Prometheus, Grafana images
task update-container-ollama  # pull/restart ollama/ollama container (with up-container-ollama)
task restart -- <svc>   # restart one service
task logs -- <svc>      # follow logs
task status             # show containers + endpoints
task reset              # stop + delete all volumes (destructive)
task pull -- <model>    # pull a model
task list               # list local models
task ps                 # show loaded models
task rm-model -- <m>    # delete a model
task test-ollama        # smoke-test Ollama connection
task orb-check          # verify OrbStack / localhost router + Ollama
task setup-cursor       # write ~/.cursor/mcp.json
task setup-claude-desktop  # write Claude Desktop MCP config
task ext-install        # build VS Code extension
task ext-package        # package extension as .vsix
task ext-dev            # watch mode for extension TS
```

---

## Troubleshooting

**Ollama not reachable**
```bash
# Default: ensure native Ollama is running on the host (port 11434), then task up
curl -sf http://localhost:11434/api/tags

# If you use task up-container-ollama instead:
task logs -- ollama
```

**Smart router not reachable**
```bash
task logs -- router
task restart -- router
```

**Extension: Python backend not found**
- Run `task ext-install` from `vscode-extension/` directory first
- Check `Ollama Local LLM` output channel in VS Code for the exact path

**Model pull times out**
- Large models (70B) take 10–30 min; use `task pull -- modelname` from terminal for progress output

**Port conflicts**
Edit `docker/compose.yaml` to change host ports (left side of `x:y` mappings).
