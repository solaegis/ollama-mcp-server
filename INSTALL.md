# Quick Install Guide

## 🎯 Choose Your Method

### 1. NPM (Best for Node.js users)

```bash
npm install -g @lvavasour/ollama-mcp-server
```

**Configure:**
```json
{
  "mcpServers": {
    "ollama": {
      "command": "ollama-mcp-server"
    }
  }
}
```

---

### 2. Homebrew (Best for Mac users)

```bash
brew tap lvavasour/tap
brew install ollama-mcp-server
```

Configuration is automatic!

---

### 3. NPX (No Installation)

**Just add to config:**
```json
{
  "mcpServers": {
    "ollama": {
      "command": "npx",
      "args": ["-y", "@lvavasour/ollama-mcp-server"]
    }
  }
}
```

Works immediately without any installation!

---

### 4. From Source (For Developers)

```bash
git clone https://github.com/lvavasour/ollama-mcp-server.git
cd ollama-mcp-server
chmod +x setup.sh
./setup.sh
```

**Configure:**
```json
{
  "mcpServers": {
    "ollama": {
      "command": "node",
      "args": ["/full/path/to/ollama-mcp-server/dist/index.js"]
    }
  }
}
```

---

## 📍 Configuration Locations

### Claude Desktop
`~/Library/Application Support/Claude/claude_desktop_config.json`

### Antigravity
Settings → MCP Servers → Add Server

### Cline/VSCode
`.vscode/settings.json` or User Settings

---

## ✅ Verify Installation

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test the MCP server
npx @modelcontextprotocol/inspector ollama-mcp-server
```

---

## 🎓 First Steps

After installation:

1. **Ensure Ollama is running**: `ollama serve`
2. **Pull a model**: `ollama pull llama3.1:8b`
3. **Restart your MCP client** (Claude Desktop, etc.)
4. **Test**: Ask Claude "List my available Ollama models"

---

## 🚀 Recommended Method

**For most users**: Use **NPX** (Option 3)
- ✅ No installation needed
- ✅ Always uses latest version
- ✅ Works everywhere
- ✅ Zero maintenance

Just add the config and go!
