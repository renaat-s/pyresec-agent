#!/usr/bin/env python3
"""
PYRESEC Git Scraper — Automated Outbound Lead Generation

Scans GitHub for recently pushed repos containing Web3 configs or FastAPI
infrastructure, extracts author emails from commits, and sends cold
outreach via Resend.

Usage:
    python scripts/git_scraper.py
    python scripts/git_scraper.py --dry-run
    python scripts/git_scraper.py --max-repos 20

Environment Variables:
    GITHUB_TOKEN        — GitHub personal access token (optional, raises rate limit)
    RESEND_API_KEY      — Resend API key for email delivery
    PYRESEC_URL         — PYRESEC API base URL (default: production)
    PYRESEC_SENDER      — Verified sender email in Resend (default: pyresec@nanoclone-systems-main.vercel.app)
    DRY_RUN             — Set to "true" to preview without sending emails
"""

import os
import sys
import json
import time
import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

# ==================== CONFIGURATION ====================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
PYRESEC_URL = os.getenv(
    "PYRESEC_URL",
    "https://pyresec-agent-519576377065.us-central1.run.app"
)
PYRESEC_SENDER = os.getenv("PYRESEC_SENDER", "pyresec@nanoclone-systems-main.vercel.app")
PYRESEC_FROM_NAME = os.getenv("PYRESEC_FROM_NAME", "PYRESEC Agent")

# GitHub Search queries — repos pushed in last 48h with Web3 or FastAPI configs
SEARCH_QUERIES = [
    "foundry.toml filename:foundry.toml pushed:>={date}",
    "hardhat.config.js filename:hardhat.config.js pushed:>={date}",
    "hardhat.config.ts filename:hardhat.config.ts pushed:>={date}",
    "fastapi filename:main.py pushed:>={date}",
    "requirements.txt fastapi filename:requirements.txt pushed:>={date}",
]

# Deduplication file
SEEN_REPOS_FILE = "scripts/.seen_repos.json"

# Rate limiting
GITHUB_API_DELAY = 2.0  # seconds between GitHub API calls (unauthenticated: 10/min)
RESEND_API_DELAY = 0.5  # seconds between emails


# ==================== GITHUB API ====================

def github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def search_repos(query: str, per_page: int = 10) -> list[dict]:
    """Search GitHub for recently pushed repos matching a query."""
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": per_page,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=github_headers(), params=params)

        if resp.status_code == 403:
            print(f"  [RATE LIMITED] GitHub API rate limit hit. Waiting 60s...")
            time.sleep(60)
            resp = client.get(url, headers=github_headers(), params=params)

        if resp.status_code != 200:
            print(f"  [ERROR] GitHub search returned {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        return data.get("items", [])


def get_commit_author(repo_full_name: str, since: str) -> Optional[dict]:
    """Get the most recent commit author email for a repo."""
    url = f"https://api.github.com/repos/{repo_full_name}/commits"
    params = {"since": since, "per_page": 1}

    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=github_headers(), params=params)

        if resp.status_code != 200:
            return None

        commits = resp.json()
        if not commits:
            return None

        commit = commits[0]
        author = commit.get("commit", {}).get("author", {})
        email = author.get("email", "")

        # Skip noreply emails
        if not email or "noreply" in email or "users.noreply" in email:
            return None

        return {
            "name": author.get("name", ""),
            "email": email,
            "date": author.get("date", ""),
            "message": commit.get("commit", {}).get("message", "")[:100],
        }


def load_seen_repos() -> set:
    """Load previously contacted repos to avoid duplicates."""
    if os.path.exists(SEEN_REPOS_FILE):
        with open(SEEN_REPOS_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("repos", []))
    return set()


def save_seen_repos(seen: set):
    """Save contacted repos."""
    with open(SEEN_REPOS_FILE, "w") as f:
        json.dump({"repos": list(seen), "updated": datetime.now(timezone.utc).isoformat()}, f, indent=2)


# ==================== EMAIL TEMPLATES ====================

def build_email_body(repo_name: str, repo_url: str, file_type: str) -> str:
    """Build a short, text-only developer outreach email."""
    tool_name = "FastAPI" if file_type == "fastapi" else "Web3/Smart Contract"

    return f"""Hey,

Noticed you just pushed a new {tool_name} project to GitHub ({repo_name}).

If you want a quick security check, run this to send a micro-audit straight to your terminal — no account needed:

curl -X POST {PYRESEC_URL}/v1/audit/quick-scan \\
  -H "Content-Type: application/json" \\
  -d '{{"code": "<your-main-file>"}}'

$0.01 USDC on Base. Top 3 vulnerabilities with CWE IDs and line numbers.

Full audit: $0.50 | Auto-patch: $5.00

Docs: {PYRESEC_URL}/docs
MCP: {PYRESEC_URL}/mcp/manifest.json

— PYRESEC Agent
NanoClone Life Sciences Ltd.
"""


def build_email_subject(repo_name: str, file_type: str) -> str:
    """Build a compelling subject line."""
    if file_type == "fastapi":
        return f"Quick security check for {repo_name}?"
    return f"Security audit for your {repo_name} contract?"


# ==================== RESEND EMAIL ====================

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email via Resend API."""
    if not RESEND_API_KEY:
        print("  [SKIP] RESEND_API_KEY not set — cannot send emails")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": f"{PYRESEC_FROM_NAME} <{PYRESEC_SENDER}>",
        "to": [to_email],
        "subject": subject,
        "text": body,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json=payload)

        if resp.status_code == 200 or resp.status_code == 201:
            return True
        else:
            print(f"  [EMAIL ERROR] {resp.status_code}: {resp.text[:200]}")
            return False


# ==================== MAIN PIPELINE ====================

def run_scraper(dry_run: bool = False, max_repos: int = 30):
    """Main scraper pipeline."""
    print("=" * 60)
    print("  PYRESEC Git Scraper — Outbound Lead Generation")
    print("=" * 60)
    print()

    date_threshold = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    seen = load_seen_repos()
    contacted = 0
    skipped = 0

    for query_template in SEARCH_QUERIES:
        query = query_template.format(date=date_threshold)
        print(f"[SEARCH] {query[:60]}...")

        repos = search_repos(query, per_page=10)
        time.sleep(GITHUB_API_DELAY)

        for repo in repos:
            if contacted >= max_repos:
                print(f"\n[DONE] Reached max_repos limit ({max_repos})")
                break

            full_name = repo["full_name"]
            repo_url = repo["html_url"]

            # Deduplication
            if full_name in seen:
                skipped += 1
                continue

            # Determine file type from query
            if "fastapi" in query.lower() or "requirements.txt" in query.lower():
                file_type = "fastapi"
            else:
                file_type = "web3"

            # Get commit author email
            print(f"  Checking {full_name}...")
            since = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
            author = get_commit_author(full_name, since)
            time.sleep(GITHUB_API_DELAY)

            if not author:
                print(f"    [SKIP] No public author email found")
                seen.add(full_name)
                continue

            email = author["email"]
            name = author["name"]
            print(f"    Author: {name} <{email}>")

            # Build email
            subject = build_email_subject(repo["name"], file_type)
            body = build_email_body(full_name, repo_url, file_type)

            if dry_run:
                print(f"    [DRY RUN] Would send to {email}")
                print(f"    Subject: {subject}")
            else:
                print(f"    Sending to {email}...")
                success = send_email(email, subject, body)
                if success:
                    print(f"    [SENT] Email delivered")
                    contacted += 1
                else:
                    print(f"    [FAILED] Email not sent")
                time.sleep(RESEND_API_DELAY)

            seen.add(full_name)

    # Save dedup state
    save_seen_repos(seen)

    print()
    print("=" * 60)
    print(f"  Complete. Contacted: {contacted} | Skipped (seen): {skipped}")
    print("=" * 60)


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PYRESEC Git Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending emails")
    parser.add_argument("--max-repos", type=int, default=30, help="Max repos to contact per run")
    args = parser.parse_args()

    if not RESEND_API_KEY and not args.dry_run:
        print("WARNING: RESEND_API_KEY not set. Emails will not be sent.")
        print("Set it in your environment or .env file.")
        print()

    run_scraper(dry_run=args.dry_run, max_repos=args.max_repos)
