#!/bin/bash
# Submit PYRESEC to Smithery.ai MCP Marketplace
# Run this from the PYRESEC directory after GitHub repo is live
#
# Prerequisites:
#   1. Install smithery CLI: npm install -g @smithery/cli
#   2. Server must be live at https://pyresec-agent-519576377065.us-central1.run.app
#
# Usage: bash scripts/submit-smithery.sh

set -e

echo "==========================================="
echo "  PYRESEC — Smithery.ai Submission"
echo "==========================================="
echo ""

# Check smithery CLI is installed
if ! command -v smithery &> /dev/null; then
    echo "ERROR: smithery CLI not found."
    echo "Install it: npm install -g @smithery/cli"
    exit 1
fi

echo "[1/3] Authenticating with Smithery..."
smithery auth login
echo "  OK"
echo ""

echo "[2/3] Publishing PYRESEC to Smithery..."
echo "  Server URL: https://pyresec-agent-519576377065.us-central1.run.app/mcp"
echo "  Name: @nanoclone-ltd/pyresec-agent"
echo ""

smithery mcp publish "https://pyresec-agent-519576377065.us-central1.run.app/mcp" \
    -n @nanoclone-ltd/pyresec-agent \
    --config-schema '{"type":"object","properties":{}}'

echo "  DONE"
echo ""

echo "[3/3] Verifying..."
echo "  Your Smithery page will be at:"
echo "  https://smithery.ai/server/@nanoclone-ltd/pyresec-agent"
echo ""
echo "==========================================="
echo "  PYRESEC published to Smithery!"
echo "  AI agents using Smithery will now"
echo "  discover and use PYRESEC automatically."
echo "==========================================="
