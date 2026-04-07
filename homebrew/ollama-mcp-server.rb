class OllamaMcpServer < Formula
  desc "MCP server for Ollama local LLM interface"
  homepage "https://github.com/lvavasour/ollama-mcp-server"
  url "https://github.com/lvavasour/ollama-mcp-server/archive/v1.0.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  license "MIT"

  depends_on "node"

  def install
    system "npm", "install", *Language::Node.std_npm_install_args(libexec)
    system "npm", "run", "build", "--prefix", libexec
    bin.install_symlink Dir["#{libexec}/bin/*"]
  end

  def caveats
    <<~EOS
      Ollama MCP Server installed!
      
      Configure in Claude Desktop:
        ~/Library/Application Support/Claude/claude_desktop_config.json
      
      Add:
      {
        "mcpServers": {
          "ollama": {
            "command": "#{bin}/ollama-mcp-server"
          }
        }
      }
      
      For Antigravity or other MCP clients:
        Command: #{bin}/ollama-mcp-server
        
      Ensure Ollama is running: ollama serve
    EOS
  end

  test do
    # Test that the server starts and responds
    output = shell_output("#{bin}/ollama-mcp-server --version 2>&1", 0)
    assert_match "1.0.0", output
  end
end
