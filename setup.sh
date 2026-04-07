#!/bin/bash

# Ollama MCP Server Setup Script

set -e

echo "🚀 Setting up Ollama MCP Server..."

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Ensure Ollama is running: ollama serve"
echo "2. Test the server: npm run inspect"
echo "3. Configure in your MCP client (see README.md)"
echo ""
echo "Configuration for Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):"
echo '{'
echo '  "mcpServers": {'
echo '    "ollama": {'
echo '      "command": "node",'
echo '      "args": ["'$(pwd)'/dist/index.js"],'
echo '      "env": {'
echo '        "OLLAMA_BASE_URL": "http://localhost:11434"'
echo '      }'
echo '    }'
echo '  }'
echo '}'
