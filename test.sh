#!/bin/bash

# Quick test script to verify Ollama MCP server works

set -e

echo "🧪 Testing Ollama MCP Server..."
echo ""

# Check if Ollama is running
echo "1️⃣ Checking Ollama connection..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama is running"
else
    echo "❌ Ollama is not running. Start it with: ollama serve"
    exit 1
fi

# Check if dist folder exists
echo ""
echo "2️⃣ Checking build..."
if [ -d "dist" ]; then
    echo "✅ Build directory exists"
else
    echo "❌ Build directory not found. Run: npm run build"
    exit 1
fi

# Check if index.js exists
if [ -f "dist/index.js" ]; then
    echo "✅ Server compiled successfully"
else
    echo "❌ Server not compiled. Run: npm run build"
    exit 1
fi

echo ""
echo "3️⃣ Available Ollama models:"
curl -s http://localhost:11434/api/tags | jq -r '.models[].name'

echo ""
echo "✅ All checks passed!"
echo ""
echo "To test interactively, run: npm run inspect"
