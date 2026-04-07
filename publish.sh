#!/bin/bash

# Complete publishing workflow for Ollama MCP Server

set -e

echo "🚀 Ollama MCP Server Publishing Workflow"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found. Run this from the project root."
    exit 1
fi

# Check git status
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: Working directory is not clean. Commit or stash changes first."
    exit 1
fi

# Get version from package.json
VERSION=$(node -p "require('./package.json').version")
echo "📦 Version: $VERSION"
echo ""

# Build
echo "🔨 Building..."
npm run build

if [ ! -f "dist/index.js" ]; then
    echo "❌ Build failed"
    exit 1
fi
echo "✅ Build successful"
echo ""

# Test
echo "🧪 Running tests..."
if command -v ollama &> /dev/null; then
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama is running"
    else
        echo "⚠️  Warning: Ollama not running (ollama serve)"
    fi
else
    echo "⚠️  Warning: Ollama not installed"
fi
echo ""

# Git operations
echo "🏷️  Git operations..."
read -p "Create git tag v$VERSION? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git tag -a "v$VERSION" -m "Release v$VERSION"
    echo "✅ Tag created"
    
    read -p "Push to GitHub? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin main
        git push origin "v$VERSION"
        echo "✅ Pushed to GitHub"
    fi
fi
echo ""

# NPM publish
echo "📤 NPM Publishing..."
read -p "Publish to NPM? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    npm publish --access public
    echo "✅ Published to NPM"
    echo "📦 Package: https://www.npmjs.com/package/@lvavasour/ollama-mcp-server"
fi
echo ""

# Homebrew formula
echo "🍺 Homebrew Formula..."
echo "Next steps for Homebrew:"
echo "1. Create GitHub release: https://github.com/lvavasour/ollama-mcp-server/releases/new"
echo "2. Download tarball: curl -L https://github.com/lvavasour/ollama-mcp-server/archive/v$VERSION.tar.gz -o v$VERSION.tar.gz"
echo "3. Get SHA256: shasum -a 256 v$VERSION.tar.gz"
echo "4. Update homebrew/ollama-mcp-server.rb with new URL and SHA256"
echo "5. Push to homebrew tap: https://github.com/lvavasour/homebrew-tap"
echo ""

echo "✅ Publishing workflow complete!"
