# Distribution Guide

This guide covers all the ways to distribute and install the Ollama MCP Server.

## 📦 Distribution Methods

### 1. NPM Package (Recommended)

**Advantages:**
- ✅ Cross-platform
- ✅ Easy updates
- ✅ Version management
- ✅ Familiar to developers

**Setup:**

1. Create npm account at https://www.npmjs.com
2. Login locally: `npm login`
3. Publish: `npm publish --access public`

**For Users:**
```bash
npm install -g @lvavasour/ollama-mcp-server
```

**Configuration:**
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

### 2. NPX (Zero Install)

**Advantages:**
- ✅ No installation required
- ✅ Always latest version
- ✅ Zero maintenance
- ✅ Works everywhere

**For Users:**

Just configure - no installation needed!

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

---

### 3. Homebrew Formula (Mac Only)

**Advantages:**
- ✅ Native Mac experience
- ✅ Automatic dependency management
- ✅ System integration
- ✅ Easy updates via `brew upgrade`

**Setup:**

1. Create GitHub repository for homebrew tap:
   ```bash
   gh repo create homebrew-tap --public
   ```

2. Clone and add formula:
   ```bash
   git clone https://github.com/lvavasour/homebrew-tap.git
   cd homebrew-tap
   mkdir -p Formula
   cp /path/to/ollama-mcp-server/homebrew/ollama-mcp-server.rb Formula/
   ```

3. Update formula with actual SHA256:
   ```bash
   # Create release on GitHub first
   curl -L https://github.com/lvavasour/ollama-mcp-server/archive/v1.0.0.tar.gz -o v1.0.0.tar.gz
   shasum -a 256 v1.0.0.tar.gz
   # Update SHA256 in Formula/ollama-mcp-server.rb
   ```

4. Commit and push:
   ```bash
   git add Formula/ollama-mcp-server.rb
   git commit -m "Add ollama-mcp-server formula"
   git push origin main
   ```

**For Users:**
```bash
brew tap lvavasour/tap
brew install ollama-mcp-server
```

---

### 4. One-Command Install Script

**Advantages:**
- ✅ Simplest for end users
- ✅ Automatic setup
- ✅ Platform detection
- ✅ Configuration guidance

**Setup:**

Host `install.sh` on GitHub, then users can run:

```bash
curl -fsSL https://raw.githubusercontent.com/lvavasour/ollama-mcp-server/main/install.sh | bash
```

---

### 5. GitHub Releases (Manual Download)

**Advantages:**
- ✅ No external dependencies
- ✅ Full control
- ✅ Works offline after download

**Setup:**

1. Build locally: `npm run build`
2. Create tarball: `tar -czf ollama-mcp-server-v1.0.0.tar.gz dist/ package.json README.md LICENSE`
3. Create GitHub release and attach tarball

**For Users:**
```bash
# Download release
curl -L https://github.com/lvavasour/ollama-mcp-server/releases/download/v1.0.0/ollama-mcp-server-v1.0.0.tar.gz -o ollama-mcp-server.tar.gz

# Extract
tar -xzf ollama-mcp-server.tar.gz
cd ollama-mcp-server

# Use
node dist/index.js
```

---

## 🚀 Publishing Workflow

### Initial Setup

1. **Initialize repository:**
   ```bash
   chmod +x init-repo.sh
   ./init-repo.sh
   ```

2. **Create GitHub repository:**
   ```bash
   gh repo create ollama-mcp-server --public
   git remote add origin https://github.com/lvavasour/ollama-mcp-server.git
   ```

3. **First commit:**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

### Publishing New Version

**Option A: Automated (Recommended)**

1. Update version in `package.json`
2. Commit changes
3. Create and push tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. GitHub Actions automatically publishes to NPM

**Option B: Manual**

```bash
chmod +x publish.sh
./publish.sh
```

This script will:
- Build the project
- Create git tag
- Push to GitHub
- Publish to NPM
- Provide Homebrew instructions

### NPM Publishing Requirements

1. **Create NPM account**: https://www.npmjs.com/signup
2. **Generate access token**: 
   - Go to npmjs.com → Account → Access Tokens
   - Generate new token (Automation type)
3. **Add to GitHub secrets**:
   - GitHub repo → Settings → Secrets → New repository secret
   - Name: `NPM_TOKEN`
   - Value: Your NPM token

---

## 📊 Comparison Table

| Method | Ease of Install | Ease of Update | Platform | Maintenance |
|--------|----------------|----------------|----------|-------------|
| NPM Global | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | All | Low |
| NPX | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | All | None |
| Homebrew | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Mac only | Medium |
| Install Script | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | All | Low |
| Manual | ⭐⭐ | ⭐ | All | High |

---

## 🎯 Recommended Distribution Strategy

**For Public Release:**

1. **Primary**: NPM package (`@lvavasour/ollama-mcp-server`)
2. **Zero-install**: Document NPX method prominently
3. **Mac users**: Create Homebrew tap
4. **One-liner**: Provide install script for quick setup

**Documentation Priority:**

1. NPX method (in README.md hero section)
2. NPM global install
3. Homebrew (for Mac)
4. Manual/source install

This maximizes reach while minimizing user friction.

---

## 🔄 Update Strategy

**Semantic Versioning:**
- **Major** (1.0.0 → 2.0.0): Breaking changes
- **Minor** (1.0.0 → 1.1.0): New features
- **Patch** (1.0.0 → 1.0.1): Bug fixes

**Release Checklist:**

- [ ] Update CHANGELOG.md
- [ ] Update version in package.json
- [ ] Run tests
- [ ] Build successfully
- [ ] Commit changes
- [ ] Create git tag
- [ ] Push tag (triggers CI/CD)
- [ ] Verify NPM publish
- [ ] Update Homebrew formula (if changed)
- [ ] Create GitHub release with notes

---

## 📣 Announcement Template

```markdown
🚀 Ollama MCP Server v1.0.0 Released!

Access your local Ollama models through MCP in Claude, Antigravity, and other MCP clients.

**Quick Install:**
```bash
npx @lvavasour/ollama-mcp-server
```

No installation needed! Just add to your MCP config:
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

**Features:**
- 🔍 List local models
- 💬 Chat conversations
- ⚡ Text generation
- 🎯 Embeddings

Docs: https://github.com/lvavasour/ollama-mcp-server
```
