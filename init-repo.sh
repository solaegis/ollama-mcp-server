#!/bin/bash

# Initialize git repository and prepare for publishing

set -e

echo "🎯 Initializing Ollama MCP Server repository..."
echo ""

# Initialize git if not already
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    git branch -M main
    echo "✅ Git initialized"
else
    echo "✅ Git repository exists"
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo "Creating .gitignore..."
    cat > .gitignore <<'EOF'
node_modules/
dist/
*.log
.DS_Store
.env
EOF
    echo "✅ .gitignore created"
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
npm install

# Build
echo ""
echo "🔨 Building..."
npm run build

# Git add
echo ""
echo "📝 Staging files..."
git add .

echo ""
echo "✅ Repository initialized!"
echo ""
echo "Next steps:"
echo "1. Create GitHub repository: gh repo create ollama-mcp-server --public"
echo "2. Commit: git commit -m 'Initial commit'"
echo "3. Push: git push -u origin main"
echo "4. For NPM publishing, you'll need:"
echo "   - npm login (with your npm account)"
echo "   - npm publish --access public"
echo ""
echo "For automated publishing:"
echo "1. Add NPM_TOKEN to GitHub secrets"
echo "2. Create a tag: git tag v1.0.0"
echo "3. Push tag: git push origin v1.0.0"
echo "4. GitHub Actions will handle the rest!"
