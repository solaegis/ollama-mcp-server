# Configuration Guide

## Quick Setup

1. **Install and Build**:
   ```bash
   cd /Users/lvavasour/git/ollama-mcp-server
   chmod +x setup.sh test.sh
   ./setup.sh
   ```

2. **Test the Server**:
   ```bash
   ./test.sh
   ```

3. **Configure Your MCP Client** (see sections below)

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
      "args": ["/Users/lvavasour/git/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434"
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
- **Args**: `/Users/lvavasour/git/ollama-mcp-server/dist/index.js`
- **Environment Variables**:
  - `OLLAMA_BASE_URL=http://localhost:11434`

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
      "args": ["/Users/lvavasour/git/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434"
      }
    }
  }
}
```

---

## Environment Variables

### OLLAMA_BASE_URL
- **Default**: `http://localhost:11434`
- **Purpose**: Ollama API endpoint
- **Custom Example**: `http://192.168.1.100:11434` (remote Ollama instance)

---

## Testing Tools

### MCP Inspector
Interactive tool to test MCP servers:
```bash
npm run inspect
```

This opens a web interface where you can:
- View available tools
- Call tools with test inputs
- See responses in real-time

### Manual Testing
Test Ollama connection directly:
```bash
curl http://localhost:11434/api/tags
```

---

## Troubleshooting

### Server won't start
1. Check Ollama is running: `ollama serve`
2. Verify build completed: `ls dist/index.js`
3. Check Node version: `node --version` (needs 18+)

### Connection errors
1. Verify Ollama is accessible: `curl http://localhost:11434/api/tags`
2. Check firewall settings
3. Try explicit localhost: `OLLAMA_BASE_URL=http://127.0.0.1:11434`

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
      "args": ["/Users/lvavasour/git/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434"
      }
    },
    "ollama-remote": {
      "command": "node",
      "args": ["/Users/lvavasour/git/ollama-mcp-server/dist/index.js"],
      "env": {
        "OLLAMA_BASE_URL": "http://192.168.1.100:11434"
      }
    }
  }
}
```
