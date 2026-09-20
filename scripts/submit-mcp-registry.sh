#!/bin/bash
# Submit PYRESEC to the Official MCP Registry
# Run this from the PYRESEC directory after GitHub repo is live
#
# Prerequisites:
#   1. Install mcp-publisher: https://github.com/modelcontextprotocol/registry/releases
#   2. GitHub repo must be public at https://github.com/nanoclone-ltd/pyresec-agent
#
# Usage: bash scripts/submit-mcp-registry.sh

set -e

echo "==========================================="
echo "  PYRESEC — MCP Registry Submission"
echo "==========================================="
echo ""

# Check mcp-publisher is installed
if ! command -v mcp-publisher &> /dev/null; then
    echo "ERROR: mcp-publisher not found."
    echo "Install it from: https://github.com/modelcontextprotocol/registry/releases"
    echo ""
    echo "macOS/Linux:"
    echo '  curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr "[:upper:]" "[:lower:]")_$(uname -m | sed "s/x86_64/amd64/;s/aarch64/arm64/").tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/'
    echo ""
    echo "Windows:"
    echo '  $arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") { "arm64" } else { "amd64" }; Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"; tar xf mcp-publisher.tar.gz mcp-publisher.exe'
    exit 1
fi

echo "[1/4] Validating server.json..."
if [ ! -f "server.json" ]; then
    echo "ERROR: server.json not found. Run this from the PYRESEC directory."
    exit 1
fi
mcp-publisher validate server.json
echo "  OK - server.json is valid"
echo ""

echo "[2/4] Authenticating with MCP Registry (DNS-based auth)..."
echo "  Server name: com.nanoclone.pyresec-agent"
echo ""
echo "  You need to add a DNS TXT record for domain verification."
echo "  Run: mcp-publisher login dns"
echo "  Follow the prompts to generate and add the TXT record."
echo ""
echo "  If you haven't done this yet, press Ctrl+C and run:"
echo "    mcp-publisher login dns"
echo ""
read -p "  Press Enter to continue (if already authenticated)..."
echo ""

echo "[3/4] Publishing to MCP Registry..."
mcp-publisher publish server.json
echo "  DONE"
echo ""

echo "[4/4] Verifying..."
echo "  Search for your server at:"
echo "  https://registry.modelcontextprotocol.io/v0.1/servers?search=com.nanoclone.pyresec-agent"
echo ""
echo "==========================================="
echo "  PYRESEC published to MCP Registry!"
echo "  Claude, Cursor, and other MCP clients"
echo "  will now discover PYRESEC automatically."
echo "==========================================="
