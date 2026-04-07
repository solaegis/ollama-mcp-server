#!/bin/bash

# One-command installer for Ollama MCP Server
# Usage: curl -fsSL https://raw.githubusercontent.com/lvavasour/ollama-mcp-server/main/install.sh | bash

set -e

echo "🚀 Installing Ollama MCP Server..."
echo ""

# Detect platform
OS="$(uname -s)"
case "$OS" in
    Darwin*)    PLATFORM="macos";;
    Linux*)     PLATFORM="linux";;
    *)          PLATFORM="unknown";;
esac

echo "Platform: $PLATFORM"
echo ""

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo ""
    echo "Install Node.js first:"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  brew install node"
    else
        echo "  Visit https://nodejs.org"
    fi
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js 18+ required (found v$NODE_VERSION)"
    exit 1
fi

echo "✅ Node.js $(node -v) detected"
echo ""

# Check for npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    exit 1
fi

# Install via npm
echo "📦 Installing via npm..."
npm install -g @lvavasour/ollama-mcp-server

echo ""
echo "✅ Installation complete!"
echo ""

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Warning: Ollama is not installed"
    echo ""
    echo "Install Ollama:"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  brew install ollama"
    else
        echo "  Visit https://ollama.ai/download"
    fi
    echo ""
else
    echo "✅ Ollama detected"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama is running"
        echo ""
        echo "Available models:"
        curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4
    else
        echo "⚠️  Ollama is not running"
        echo "Start it with: ollama serve"
    fi
    echo ""
fi

# Detect MCP clients and provide configuration
echo "📋 Configuration:"
echo ""

# Claude Desktop
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ "$PLATFORM" = "macos" ] && [ -d "$HOME/Library/Application Support/Claude" ]; then
    echo "Claude Desktop detected!"
    echo "Add to: $CLAUDE_CONFIG"
    echo ""
    cat <<'EOF'
{
  "mcpServers": {
    "ollama": {
      "command": "ollama-mcp-server"
    }
  }
}
EOF
    echo ""
fi

echo "For other MCP clients, use command: ollama-mcp-server"
echo ""
echo "📚 Documentation: https://github.com/lvavasour/ollama-mcp-server"
echo ""
echo "🎉 Ready to use! Restart your MCP client and try:"
echo '   "List my available Ollama models"'
