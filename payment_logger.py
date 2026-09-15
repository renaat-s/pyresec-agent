import json
import os
from datetime import datetime
from typing import Optional

PAYMENT_LOG_FILE = "payment_log.jsonl"

def log_payment(tier, amount, payer_address=None, tx_hash=None, network="base", status="settled", client_ip=None, file_hash=None):
    entry = {"timestamp": datetime.utcnow().isoformat(), "tier": tier, "amount_usdc": amount, "payer_address": payer_address, "tx_hash": tx_hash, "network": network, "status": status, "client_ip": client_ip, "file_hash": file_hash}
    with open(PAYMENT_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[PAYMENT] ${amount:.2f} USDC | {tier} | payer={payer_address} | tx={tx_hash}")

def get_payment_logs(n=100):
    if not os.path.exists(PAYMENT_LOG_FILE):
        return []
    logs = []
    with open(PAYMENT_LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return logs[-n:]

def get_revenue_summary():
    if not os.path.exists(PAYMENT_LOG_FILE):
        return {"total_revenue": 0, "total_transactions": 0, "by_tier": {}}
    total = 0.0
    count = 0
    by_tier = {}
    with open(PAYMENT_LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                amount = entry.get("amount_usdc", 0)
                tier = entry.get("tier", "unknown")
                total += amount
                count += 1
                by_tier[tier] = by_tier.get(tier, 0) + amount
            except json.JSONDecodeError:
                continue
    return {"total_revenue": round(total, 6), "total_transactions": count, "by_tier": by_tier}
