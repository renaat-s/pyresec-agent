# PYRESEC Security Scan — GitHub Action

Scan your code for security vulnerabilities using PYRESEC AI. Pay-per-scan via x402 USDC micropayments on Base.

## Setup

1. Add your x402 wallet private key as a GitHub Secret:
   - Go to **Settings > Secrets and variables > Actions**
   - Create a new secret named `X402_WALLET_KEY`
   - Paste your Base wallet private key

2. Add the action to your workflow:

```yaml
- name: PYRESEC Security Scan
  uses: nanoclone-ltd/pyresec-scan-action@main
  with:
    code-path: ./src
    tier: quick-scan
    x402-wallet-key: ${{ secrets.X402_WALLET_KEY }}
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `code-path` | Yes | `./src` | Path to directory or file to scan |
| `tier` | No | `quick-scan` | `quick-scan` ($0.01), `deep-repo` ($0.50), or `remediate` ($5.00) |
| `x402-wallet-key` | Yes | — | Private key for x402 USDC payment on Base |
| `pyresec-url` | No | `https://pyresec-agent-519576377065.us-central1.run.app` | PYRESEC API base URL |
| `fail-on-findings` | No | `true` | Fail the workflow if vulnerabilities are found |

## Outputs

The action uploads `pyresec-results.json` as an artifact with the full scan results.

For `remediate` tier, `pyresec-patched.py` is also uploaded with the fixed code.

## Supported Languages

Python, JavaScript, TypeScript, Solidity, Go, Rust, Java

## Example: Full Workflow

```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  pyresec-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: PYRESEC Quick Scan
        uses: nanoclone-ltd/pyresec-scan-action@main
        with:
          code-path: ./src
          tier: quick-scan
          x402-wallet-key: ${{ secrets.X402_WALLET_KEY }}

      - name: PYRESEC Deep Audit (on main branch only)
        if: github.ref == 'refs/heads/main'
        uses: nanoclone-ltd/pyresec-scan-action@main
        with:
          code-path: ./src
          tier: deep-repo
          x402-wallet-key: ${{ secrets.X402_WALLET_KEY }}
```

## Pricing

Each scan costs USDC on Base Mainnet via x402 micropayments:

| Tier | Cost | What It Does |
|------|------|-------------|
| quick-scan | $0.01 | Top 3 SAST findings |
| deep-repo | $0.50 | Full OWASP + SCA + logic + gas |
| remediate | $5.00 | Auto-patched code output |
