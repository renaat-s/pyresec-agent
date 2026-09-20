#!/usr/bin/env python3
"""
PYRESEC Social Scanner — Autonomous Lead Discovery on X & Farcaster

Daemon that monitors social platforms for developers deploying Web3 or
FastAPI projects, auto-scans their public code, and generates structured
reply drafts for outbound engagement.

Usage:
    python scripts/social_scanner.py                  # Run daemon (poll loop)
    python scripts/social_scanner.py --once           # Single poll cycle
    python scripts/social_scanner.py --dry-run        # Preview without posting
    python scripts/social_scanner.py --platform x     # X only
    python scripts/social_scanner.py --platform farcaster  # Farcaster only

Environment Variables:
    PYRESEC_URL             — PYRESEC API base URL
    PYRESEC_WALLET_KEY      — Wallet key for sponsored promo scans (dev wallet)
    TWITTER_BEARER_TOKEN    — X API v2 bearer token
    WARPCAST_API_KEY        — Farcaster/Warpcast API key
    SCAN_PROMO_BUDGET       — Max sponsored scans per day (default: 10)
    POLL_INTERVAL           — Seconds between poll cycles (default: 300)
"""

import os
import sys
import json
import time
import argparse
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

import httpx

# ==================== CONFIGURATION ====================

PYRESEC_URL = os.getenv(
    "PYRESEC_URL",
    "https://pyresec-agent-519576377065.us-central1.run.app"
)
PYRESEC_WALLET_KEY = os.getenv("PYRESEC_WALLET_KEY", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
WARPCAST_API_KEY = os.getenv("WARPCAST_API_KEY", "")

SCAN_PROMO_BUDGET = int(os.getenv("SCAN_PROMO_BUDGET", "10"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))

# Keyword targets — posts/casts containing these trigger a scan
KEYWORDS = [
    "deployed my smart contract",
    "just deployed to base",
    "just deployed to ethereum",
    "my fastapi app",
    "built a fastapi",
    "new smart contract",
    "contract audit",
    "code review please",
    "security check",
    "foundry project",
    "hardhat project",
    "solidity contract",
    "base mainnet",
    "base sepolia",
    "pushed my code",
    "github.com",
]

# GitHub URL pattern — extract repos to scan
GITHUB_URL_PATTERN = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"
)

# State file — tracks seen posts to avoid duplicates
STATE_FILE = "scripts/.social_scanner_state.json"

# Daily promo scan counter
DAILY_SCANS_FILE = "scripts/.social_scans_today.json"


# ==================== PLATFORM: X (TWITTER) ====================

def search_x_posts(query: str, max_results: int = 10) -> list[dict]:
    """
    Search recent X posts using Twitter API v2.
    Requires: TWITTER_BEARER_TOKEN (Academic Research or Basic tier)
    """
    if not TWITTER_BEARER_TOKEN:
        return []

    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    params = {
        "query": f"{query} -is:retweet lang:en",
        "max_results": max(max_results, 10),
        "tweet.fields": "created_at,author_id,text,public_metrics",
        "expansions": "author_id",
        "user.fields": "name,username,public_metrics",
    }

    with httpx.Client(timeout=30.0) as client:
        try:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                includes = data.get("includes", {})
                users = {u["id"]: u for u in includes.get("users", [])}

                for tweet in data.get("data", []):
                    author = users.get(tweet.get("author_id"), {})
                    results.append({
                        "platform": "x",
                        "id": tweet["id"],
                        "text": tweet["text"],
                        "author_name": author.get("name", ""),
                        "author_username": author.get("username", ""),
                        "author_followers": author.get("public_metrics", {}).get("followers_count", 0),
                        "created_at": tweet.get("created_at", ""),
                        "url": f"https://x.com/{author.get('username', '_')}/status/{tweet['id']}",
                    })
                return results
            elif resp.status_code == 429:
                print(f"  [X RATE LIMITED] Waiting 60s...")
                time.sleep(60)
                return []
            else:
                print(f"  [X ERROR] {resp.status_code}: {resp.text[:200]}")
                return []
        except Exception as e:
            print(f"  [X ERROR] {e}")
            return []


# ==================== PLATFORM: FARCASTER ====================

def search_farcaster_casts(query: str, limit: int = 10) -> list[dict]:
    """
    Search recent Farcaster casts via Warpcast API.
    Requires: WARPCAST_API_KEY
    """
    if not WARPCAST_API_KEY:
        return []

    url = "https://api.warpcast.com/v2/search/casts"
    headers = {"Authorization": f"Bearer {WARPCAST_API_KEY}"}
    params = {"q": query, "limit": limit}

    with httpx.Client(timeout=30.0) as client:
        try:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for cast in data.get("result", {}).get("casts", []):
                    author = cast.get("author", {})
                    results.append({
                        "platform": "farcaster",
                        "id": cast.get("hash", ""),
                        "text": cast.get("text", ""),
                        "author_name": author.get("displayName", ""),
                        "author_username": author.get("username", ""),
                        "author_followers": author.get("followerCount", 0),
                        "created_at": cast.get("timestamp", ""),
                        "url": f"https://warpcast.com/{author.get('username', '_')}/{cast.get('hash', '')[:10]}",
                    })
                return results
            elif resp.status_code == 429:
                print(f"  [FARCASTER RATE LIMITED] Waiting 60s...")
                time.sleep(60)
                return []
            else:
                print(f"  [FARCASTER ERROR] {resp.status_code}: {resp.text[:200]}")
                return []
        except Exception as e:
            print(f"  [FARCASTER ERROR] {e}")
            return []


# ==================== GITHUB EXTRACTION ====================

def extract_github_urls(text: str) -> list[str]:
    """Extract GitHub repository URLs from post text."""
    return list(set(GITHUB_URL_PATTERN.findall(text)))


def fetch_github_file(repo: str, filepath: str) -> Optional[str]:
    """Fetch a file from a public GitHub repo."""
    url = f"https://raw.githubusercontent.com/{repo}/main/{filepath}"
    with httpx.Client(timeout=15.0) as client:
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
            # Try master branch
            url = url.replace("/main/", "/master/")
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
    return None


def fetch_repo_main_file(repo: str) -> Optional[str]:
    """Try to fetch the main source file from a repo."""
    candidates = [
        "main.py", "app.py", "index.js", "index.ts",
        "src/main.py", "src/app.py", "src/index.js",
        "contracts/", "src/contracts/",
    ]

    # Try common entry points
    for filepath in candidates:
        if filepath.endswith("/"):
            # It's a directory — try to list it
            continue
        content = fetch_github_file(repo, filepath)
        if content and len(content.strip()) > 50:
            return content

    return None


# ==================== PYRESEC QUICK SCAN ====================

def sponsored_quick_scan(code: str) -> Optional[dict]:
    """
    Call PYRESEC quick-scan using the dev wallet for sponsored promo scans.
    Returns scan results or None if scan fails.
    """
    if not PYRESEC_WALLET_KEY:
        print("    [SCAN] PYRESEC_WALLET_KEY not set — cannot run sponsored scan")
        return None

    # Check daily budget
    if not check_promo_budget():
        print("    [SCAN] Daily promo budget exhausted")
        return None

    try:
        import x402
        client = x402.Client(wallet_key=PYRESEC_WALLET_KEY)
        response = client.post(
            f"{PYRESEC_URL}/v1/audit/quick-scan",
            json={"code": code[:6000]}  # Limit code size for quick scan
        )

        if response.status_code == 200:
            result = response.json()
            record_promo_scan()
            return result
        else:
            print(f"    [SCAN] PYRESEC returned {response.status_code}")
            return None
    except ImportError:
        print("    [SCAN] x402 SDK not installed. Run: pip install x402")
        return None
    except Exception as e:
        print(f"    [SCAN] Error: {e}")
        return None


# ==================== DAILY BUDGET TRACKING ====================

def load_daily_scans() -> dict:
    if os.path.exists(DAILY_SCANS_FILE):
        with open(DAILY_SCANS_FILE, "r") as f:
            return json.load(f)
    return {"date": "", "count": 0}


def save_daily_scans(data: dict):
    with open(DAILY_SCANS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def check_promo_budget() -> bool:
    data = load_daily_scans()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if data.get("date") != today:
        return True
    return data.get("count", 0) < SCAN_PROMO_BUDGET


def record_promo_scan():
    data = load_daily_scans()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] = data.get("count", 0) + 1
    save_daily_scans(data)


# ==================== REPLY GENERATOR ====================

def generate_reply(post: dict, scan_result: Optional[dict], github_repo: Optional[str]) -> str:
    """
    Generate a structured Markdown reply draft.
    Returns the reply text ready to be posted.
    """
    author = post.get("author_username", "dev")
    platform = post.get("platform", "social")

    if scan_result:
        findings = scan_result.get("sast_findings", [])
        num_findings = len(findings)
        file_hash = scan_result.get("file_hash", "")[:8]

        severity_counts = {}
        for f in findings:
            sev = f.get("severity", "UNKNOWN")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        severity_str = ", ".join(f"{v} {k}" for k, v in severity_counts.items()) if severity_counts else "Clean"

        reply = f"""Hey @{author}, saw your post — ran a quick security scan on your code.

**PYRESEC Quick Scan Results:**
- Findings: {num_findings} ({severity_str})
- File hash: `{file_hash}`
- Scan tier: $0.01 USDC (sponsored)

"""
        if findings:
            reply += "**Top findings:**\n"
            for i, f in enumerate(findings[:3], 1):
                reply += f"{i}. **[{f.get('severity', '?')}]** {f.get('type', 'Unknown')} — {f.get('cwe', 'N/A')} (line {f.get('line_number', '?')})\n"

            reply += f"\nGet the full audit + auto-patch for $5.00:\n"
        else:
            reply += "Code looks clean. Want a deeper audit ($0.50) or auto-patch ($5.00)?\n"

        if github_repo:
            reply += f"\n{PYRESEC_URL}/docs"
        else:
            reply += f"\n{PYRESEC_URL}/docs"

    else:
        # No scan result — generic engagement
        reply = f"""Hey @{author}, looks like you're building something cool!

If you want a quick security check on your code, PYRESEC does SAST/SCA scans via x402 micropayments — no account needed.

$0.01 for a quick scan | $0.50 for full audit | $5.00 for auto-patch

{PYRESEC_URL}/docs"""

    return reply


# ==================== STATE MANAGEMENT ====================

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"seen_ids": [], "last_poll": {}}


def save_state(state: dict):
    # Keep only last 1000 seen IDs to prevent bloat
    state["seen_ids"] = state.get("seen_ids", [])[-1000:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def is_seen(post_id: str, state: dict) -> bool:
    return post_id in state.get("seen_ids", [])


def mark_seen(post_id: str, state: dict):
    if "seen_ids" not in state:
        state["seen_ids"] = []
    state["seen_ids"].append(post_id)


# ==================== MAIN POLL LOOP ====================

def poll_once(platforms: list[str], dry_run: bool = False, verbose: bool = True) -> list[dict]:
    """
    Single poll cycle across all platforms.
    Returns list of generated replies.
    """
    state = load_state()
    replies = []

    for keyword in KEYWORDS:
        # === X (Twitter) ===
        if "x" in platforms:
            posts = search_x_posts(keyword, max_results=5)
            for post in posts:
                if is_seen(post["id"], state):
                    continue

                if verbose:
                    print(f"\n[X] @{post['author_username']}: {post['text'][:80]}...")

                # Extract GitHub URLs
                github_urls = extract_github_urls(post["text"])
                github_repo = github_urls[0] if github_urls else None
                scan_result = None

                # If we found a GitHub repo, try to scan it
                if github_repo:
                    if verbose:
                        print(f"  Found repo: {github_repo}")
                    code = fetch_repo_main_file(github_repo)
                    if code:
                        if verbose:
                            print(f"  Scanning {len(code)} chars of code...")
                        scan_result = sponsored_quick_scan(code)

                # Generate reply
                reply = generate_reply(post, scan_result, github_repo)
                replies.append({
                    "platform": "x",
                    "post": post,
                    "reply": reply,
                    "scanned": scan_result is not None,
                })

                if verbose:
                    print(f"  Reply draft:\n{reply[:200]}...")

                mark_seen(post["id"], state)

            time.sleep(2)  # Rate limit between platforms

        # === Farcaster ===
        if "farcaster" in platforms:
            casts = search_farcaster_casts(keyword, limit=5)
            for cast in casts:
                if is_seen(cast["id"], state):
                    continue

                if verbose:
                    print(f"\n[FARCASTER] @{cast['author_username']}: {cast['text'][:80]}...")

                github_urls = extract_github_urls(cast["text"])
                github_repo = github_urls[0] if github_urls else None
                scan_result = None

                if github_repo:
                    if verbose:
                        print(f"  Found repo: {github_repo}")
                    code = fetch_repo_main_file(github_repo)
                    if code:
                        if verbose:
                            print(f"  Scanning {len(code)} chars of code...")
                        scan_result = sponsored_quick_scan(code)

                reply = generate_reply(cast, scan_result, github_repo)
                replies.append({
                    "platform": "farcaster",
                    "post": cast,
                    "reply": reply,
                    "scanned": scan_result is not None,
                })

                if verbose:
                    print(f"  Reply draft:\n{reply[:200]}...")

                mark_seen(cast["id"], state)

            time.sleep(2)

    save_state(state)
    return replies


def run_daemon(platforms: list[str], dry_run: bool = False):
    """Continuous poll loop."""
    print("=" * 60)
    print("  PYRESEC Social Scanner — Autonomous Lead Discovery")
    print("=" * 60)
    print(f"  Platforms: {', '.join(platforms)}")
    print(f"  Poll interval: {POLL_INTERVAL}s")
    print(f"  Promo budget: {SCAN_PROMO_BUDGET}/day")
    print(f"  Dry run: {dry_run}")
    print(f"  Keywords: {len(KEYWORDS)}")
    print("=" * 60)

    if not TWITTER_BEARER_TOKEN and "x" in platforms:
        print("\n[WARNING] TWITTER_BEARER_TOKEN not set — X scanning disabled")
    if not WARPCAST_API_KEY and "farcaster" in platforms:
        print("\n[WARNING] WARPCAST_API_KEY not set — Farcaster scanning disabled")

    while True:
        try:
            print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Polling...")
            replies = poll_once(platforms, dry_run=dry_run)

            if replies:
                print(f"\n  Generated {len(replies)} reply drafts")
                for r in replies:
                    print(f"    [{r['platform']}] @{r['post']['author_username']} — scanned: {r['scanned']}")
            else:
                print("  No new leads found")

        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Stopping scanner...")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")

        print(f"  Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PYRESEC Social Scanner")
    parser.add_argument("--once", action="store_true", help="Single poll cycle then exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode — no scans posted")
    parser.add_argument("--platform", choices=["x", "farcaster", "all"], default="all",
                        help="Platform to scan (default: all)")
    parser.add_argument("--verbose", action="store_true", default=True, help="Verbose output")
    args = parser.parse_args()

    platform_map = {
        "x": ["x"],
        "farcaster": ["farcaster"],
        "all": ["x", "farcaster"],
    }
    platforms = platform_map[args.platform]

    if args.once:
        replies = poll_once(platforms, dry_run=args.dry_run, verbose=args.verbose)
        print(f"\n{'='*60}")
        print(f"  Scan complete. {len(replies)} replies generated.")
        print(f"{'='*60}")
        for i, r in enumerate(replies, 1):
            print(f"\n--- Reply {i} [{r['platform']}] ---")
            print(r["reply"])
    else:
        run_daemon(platforms, dry_run=args.dry_run)
