# ollama-mcp-server

Local LLM stack for Mac — Ollama runtime, OpenAI-compatible proxy, MCP server for Claude/Cursor/Antigravity, and a VS Code extension with model picker and selection tools.

## What's included

| Component | Purpose |
|---|---|
| **MCP server** (`src/`) | Exposes Ollama tools to any MCP client: list, generate, chat, embeddings |
| **Docker stack** (`docker/`) | Ollama + LiteLLM proxy + Open WebUI + Prometheus + Grafana |
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
```

Ollama itself runs inside the Docker stack — no host install needed.

---

## Quick start

```bash
cd ~/git/solaegis/ollama-mcp-server

# 1. Build the MCP server
task build

# 2. Copy and edit environment (change keys, adjust default models)
cp .env.example .env

# 3. Start the full Docker stack
#    Pulls default models automatically on first run
task up

# 4. Verify everything
task test-ollama      # lists available models
task test-litellm     # smoke-tests OpenAI-compatible endpoint

# 5. Wire MCP into Cursor (writes ~/.cursor/mcp.json)
task setup-cursor

# 6. Wire MCP into Claude Desktop
task setup-claude-desktop
```

### Service endpoints after `task up`

| Service | URL | Purpose |
|---|---|---|
| Ollama API | `http://localhost:11434` | Direct model API |
| LiteLLM proxy | `http://localhost:4000` | OpenAI-compatible (direct or behind router) |
| Smart router | `http://localhost:4001` | OpenAI-compatible + classifier; **use this for Cursor / Commit Sage** |
| Open WebUI | `http://localhost:8080` | Browser chat UI |
| Grafana | `http://localhost:3001` | Usage metrics |
| Prometheus | `http://localhost:9090` | Raw metrics |

---

## Choosing an agent (or provider)

Cursor and other clients can use **several** “agents” or backends at once. Use this as a rule of thumb:

| Use this | When |
|---|---|
| **Cursor cloud / subscription models** (default Chat, Composer, etc.) | Hard problems: architecture, large refactors, debugging across many files, planning, or when you need the strongest available model. |
| **MCP tools** (`ollama_task`, `ollama_summarize`, `ollama_git_commit`, …) | Offload **repetitive or token-heavy** work to **local** models: conventional commits from diffs, long summaries, embeddings, quick local checks. Saves **context and cost** on the cloud agent; the **smart router** picks a model from prompt content when the tool uses `model: auto`. Prefer these tools in the **agent** chat when the task does not need frontier reasoning. |
| **OpenAI-compatible override → smart router** (`http://localhost:4001/v1`, model `auto` or a LiteLLM alias) | **Local** Chat sessions that should follow the same **routing** as MCP (code vs docs vs summarization, etc.). Use **Verify** so `GET /v1/models` populates the list. Not every Composer surface respects custom providers—if in doubt, use **Chat** or **MCP** for local routing. |
| **VS Code / Cursor extension** (`Ollama: …` commands) | **Editor-native** flows: send selection, rewrite selection, side chat panel, model picker. Calls **Ollama directly** by default (not the smart router) unless you point integration at LiteLLM/router yourself. |

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
| `phi4:latest` | General, fast | ~9 GB |
| `llama3.3:70b` | Deep reasoning | ~45 GB |
| `nomic-embed-text` | Embeddings | ~300 MB |

All four can be loaded simultaneously on the M2 Ultra.

---

## IDE integration

### Cursor

`task setup-cursor` writes the MCP config automatically. To do it manually:

`~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["/Users/lvavasour/git/solaegis/ollama-mcp-server/dist/index.js"],
      "env": { "OLLAMA_BASE_URL": "http://localhost:11434" }
    }
  }
}
```

For the **OpenAI-compatible provider** (Cursor chat/composer using local models), point at the **smart router** (port **4001**) so requests can be classified (code vs docs vs **git commit**, etc.):

Cursor Settings → Models → OpenAI override (or `cursor.openai.apiBase` / `cursor.openai.apiKey` in `settings.json`):
- API Base: `http://localhost:4001/v1` (or `http://ollama-router.ollama-stack.orb.local:4001/v1` when using OrbStack hostnames from `task setup-cursor`). The router proxies **`GET /v1/models`** to LiteLLM so Cursor can **discover** model IDs (use **Verify** if the list is empty).
- API Key: `sk-local-dev-key` (same as `LITELLM_MASTER_KEY` in `.env`)
- Model: `auto` or `router` for automatic routing; or `commit` / `commit-sage` to force the git-commit model; or any `model_name` from `config/litellm.yaml` (e.g. `qwen2.5-coder-7b`) for a fixed model.
- `task sync-cursor-models` writes a reference list under `~/.cursor/ollama-router-model-list.json` and checks `GET /v1/models`; it does **not** populate Cursor’s Settings UI (Cursor reads models from the API, not arbitrary `settings.json` keys).

**Commit Sage** (VS Code / Cursor extension `VizzleTF.geminicommit`): set provider to **OpenAI**, **Base URL** `http://localhost:4001/v1`, API key as above, and keep default model **`gpt-3.5-turbo`** — the router upgrades to **`qwen2.5-coder-14b`** when the prompt looks like a diff/commit. To force the commit model without classification, set model to **`commit`** or **`commit-sage`**.

### Windsurf

Settings → AI Providers → Add Custom:
- Base URL: `http://localhost:4000/v1`
- API Key: `sk-local-dev-key`

### Zed

`~/.config/zed/settings.json`:
```json
{
  "language_models": {
    "openai": {
      "api_url": "http://localhost:4000/v1",
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
- Env: `OLLAMA_BASE_URL=http://localhost:11434`

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
| `ollama.litellmUrl` | `http://localhost:4000` | LiteLLM proxy URL |
| `ollama.defaultModel` | `qwen2.5-coder:7b` | Active model |
| `ollama.temperature` | `0.7` | Sampling temperature |

### Status bar indicators

```
● qwen2.5-coder:7b +stack   — model loaded in memory, LiteLLM running
○ qwen2.5-coder:7b          — model available but not yet loaded
✕ qwen2.5-coder:7b          — Ollama unreachable
```

---

## MCP tools reference

Once wired into Cursor/Claude Desktop, these tools are available to the AI agent:

| Tool | Description |
|---|---|
| `ollama_list_models` | List all pulled models |
| `ollama_generate` | Single-turn prompt → response |
| `ollama_chat` | Multi-turn conversation with message history |
| `ollama_embeddings` | Generate vector embeddings |

Example usage in Cursor Agent:
```
Use ollama_chat with qwen2.5-coder:7b to rewrite this prompt to be more specific
```

---

## Adding models to LiteLLM routing

Edit `config/litellm.yaml` → add to `model_list`:
```yaml
- model_name: my-alias
  litellm_params:
    model: ollama/modelname:tag
    api_base: os.environ/OLLAMA_BASE_URL
```

Restart the proxy: `task restart -- litellm`

---

## All task commands

```bash
task build              # install npm deps + compile MCP server TypeScript
task inspect            # launch MCP Inspector (browser UI for testing tools)
task up                 # start full Docker stack
task down               # stop stack (volumes kept)
task restart -- <svc>   # restart one service
task logs -- <svc>      # follow logs
task status             # show containers + endpoints
task reset              # stop + delete all volumes (destructive)
task pull -- <model>    # pull a model
task list               # list local models
task ps                 # show loaded models
task rm-model -- <m>    # delete a model
task test-ollama        # smoke-test Ollama connection
task test-litellm       # smoke-test LiteLLM endpoint
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
task logs -- ollama
# Usually: model still loading, or port conflict on 11434
```

**LiteLLM not starting**
```bash
task logs -- litellm
# Usually: config/litellm.yaml syntax error, or Ollama not healthy yet
```

**Extension: Python backend not found**
- Run `task ext-install` from `vscode-extension/` directory first
- Check `Ollama Local LLM` output channel in VS Code for the exact path

**Model pull times out**
- Large models (70B) take 10–30 min; use `task pull -- modelname` from terminal for progress output

**Port conflicts**
Edit `docker/compose.yaml` to change host ports (left side of `x:y` mappings).
