# Configuration Guide

## Quick setup

From the repo root (replace the path with your clone):

```bash
cd ~/git/solaegis/ollama-mcp-server
cp .env.example .env
task build
task up          # Docker stack + native Ollama on host :11434 (see README)
task test-ollama
```

Then wire your MCP client (sections below).

---

## Default stack (native Ollama on Mac)

`task up` merges [docker/compose.hybrid-host.yaml](docker/compose.hybrid-host.yaml) so **router**, **Open WebUI**, **model-puller**, and **Prometheus** call **`http://host.docker.internal:11434`** (native Ollama on the host, Metal). Docker’s **`extra_hosts: host.docker.internal:host-gateway`** (in that override file) makes the hostname resolve from Linux containers on Mac/Windows. The **`ollama` Docker service** is **off** unless you run **`task up-container-ollama`** (`--profile docker-ollama`).

- **Breaking change** if you previously relied on `task up` to start the Linux `ollama` container: use **`task up-container-ollama`** and **`task down-container-ollama`**, and free host port **11434** for the container.

---

## Ollama OpenAI compatibility and this stack

Official reference: [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility).

| Topic | Guidance |
|-------|----------|
| **OpenAI client base URL** | Must end with **`/v1`** when using Cursor, Windsurf, or other OpenAI SDKs against the router (`http://localhost:4001/v1`) or Ollama directly (`http://localhost:11434/v1`). |
| **API key** | SDKs often require a non-empty key; Ollama **ignores** it. Use any placeholder (e.g. `sk-local-dev-key`). |
| **Unsupported chat fields** | Fields such as **`tool_choice`**, **`logit_bias`**, **`user`**, **`n`**, **`logprobs`** may be unsupported or ignored — see the official table. |
| **`ROUTER_BASE_URL` / MCP** | Set to the router **origin only** (e.g. `http://localhost:4001`) — **no** `/v1` suffix. The Node MCP client appends `/v1/chat/completions` and `/route`. |
| **`OLLAMA_BASE_URL` (router container)** | **Server-side only** in Compose: single **trusted** upstream Ollama instance. Do not point this at user-controlled URLs. |
| **`GET /v1/models` on the router** | **Synthetic** list for client discovery; use `ollama list` or `GET http://localhost:11434/api/tags` for installed models. |
| **Streaming / metrics** | Router buffers the full upstream HTTP response before returning it; Prometheus token counters from `usage` align with **non-streaming** JSON responses (see README *Grafana token panels* troubleshooting). |

---

## Claude Desktop Configuration

### Location
`~/Library/Application Support/Claude/claude_desktop_config.json`

### Configuration
```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["/path/to/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "ROUTER_BASE_URL": "http://localhost:4001"
      }
    }
  }
}
```

### Restart Required
After adding configuration, restart Claude Desktop completely (Cmd+Q and reopen).

---

## Antigravity Configuration

### Settings Location
Open Antigravity → Settings → MCP Servers

### Add Server
- **Name**: Ollama
- **Type**: stdio
- **Command**: `node`
- **Args**: `/path/to/ollama-mcp-server/dist/index.js`
- **Environment Variables**:
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `ROUTER_BASE_URL=http://localhost:4001`

---

## Cline/VSCode Configuration

### Location
`.vscode/settings.json` or global VSCode settings

### Configuration
```json
{
  "cline.mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["/path/to/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "ROUTER_BASE_URL": "http://localhost:4001"
      }
    }
  }
}
```

---

## Environment Variables

### OLLAMA_BASE_URL
- **Default**: `http://localhost:11434` (native Ollama on the host for the default `task up` stack)
- **Purpose**: Ollama API endpoint for MCP tools
- **Custom Example**: `http://192.168.1.100:11434` (remote Ollama instance)

### ROUTER_BASE_URL
- **Default**: `http://localhost:4001` (smart router in Docker, published on host port 4001)
- **Purpose**: MCP tools that call the OpenAI-compatible router use this base (no `/v1` suffix; see server code).
- **OrbStack / SSRF**: optional `http://router.ollama-stack.orb.local:4001` — Cursor `setup-cursor` can set MCP to this when run with `OLLAMA_MCP_USE_ORB_DNS=1`. For Cursor’s **OpenAI-compatible** override (not MCP), use a base URL ending in **`/v1`** on the same host/port family (see README).

---

## Verification (curl)

After `task up` (or with the router running on the host):

```bash
# Native Ollama — list pulled models (ground truth)
curl -sfS http://localhost:11434/api/tags | head

# Smart router
curl -sfS http://localhost:4001/health
curl -sfS http://localhost:4001/v1/models | head

# Classification only (no LLM call)
curl -sfS http://localhost:4001/route \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"fix this rust compile error"}]}'
```

OpenAI-style clients use **`http://localhost:4001/v1`** as the API base (trailing **`/v1`**, no extra path).

---

## Testing Tools

### MCP Inspector
Interactive tool to test MCP servers (from repo root):

```bash
task inspect
```

This opens a web interface where you can:
- View available tools
- Call tools with test inputs
- See responses in real-time

### Manual Testing
Test Ollama connection directly:

```bash
curl -sfS http://localhost:11434/api/tags
```

---

## Troubleshooting

### Server won't start
1. Check Ollama is running: `ollama serve`
2. Verify build completed: `ls dist/index.js`
3. Check Node version: `node --version` (needs 18+)

### Connection errors
1. Verify Ollama is accessible: `curl -sfS http://localhost:11434/api/tags`
2. Verify router: `curl -sfS http://localhost:4001/health`
3. Check firewall settings
4. Try explicit localhost: `OLLAMA_BASE_URL=http://127.0.0.1:11434`

### Model not found
Pull models first:
```bash
ollama pull llama3.1:8b
ollama list
```

### Permission errors
Ensure scripts are executable:
```bash
chmod +x setup.sh test.sh
```

---

## Usage Examples

Once configured, use in your MCP client:

### List Models
```
"Show me what Ollama models are available"
```

### Generate Text
```
"Use Ollama with llama3.1:8b to explain quantum computing"
```

### Chat Conversation
```
"Start a chat with llama3.1 about software architecture patterns"
```

### Generate Embeddings
```
"Create embeddings for this text using Ollama: 'machine learning is fascinating'"
```

---

## Multiple Ollama Instances

To connect to multiple Ollama instances, add multiple server configs:

```json
{
  "mcpServers": {
    "ollama-local": {
      "command": "node",
      "args": ["/path/to/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "ROUTER_BASE_URL": "http://localhost:4001"
      }
    },
    "ollama-remote": {
      "command": "node",
      "args": ["/path/to/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://192.168.1.100:11434",
        "ROUTER_BASE_URL": "http://localhost:4001"
      }
    }
  }
}
```
