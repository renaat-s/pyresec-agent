import os
import json
from datetime import datetime

MONTHLY_SPENDING_LIMIT = float(os.getenv("MONTHLY_SPENDING_LIMIT", "50.00"))
DAILY_TRANSFER_LIMIT = float(os.getenv("DAILY_TRANSFER_LIMIT", "10.00"))
MAX_SINGLE_TRANSFER = float(os.getenv("MAX_SINGLE_TRANSFER", "5.00"))
APPROVED_DESTINATIONS_FILE = "approved_destinations.json"
SPENDING_LOG_FILE = "spending_log.json"

def load_approved_destinations():
    if os.path.exists(APPROVED_DESTINATIONS_FILE):
        with open(APPROVED_DESTINATIONS_FILE, "r") as f:
            return json.load(f)
    return []

def load_spending_log():
    if os.path.exists(SPENDING_LOG_FILE):
        with open(SPENDING_LOG_FILE, "r") as f:
            return json.load(f)
    return {"daily": {}, "monthly": {}}

def save_spending_log(log):
    with open(SPENDING_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def get_month_key():
    return datetime.utcnow().strftime("%Y-%m")

def get_day_key():
    return datetime.utcnow().strftime("%Y-%m-%d")

def check_spending_limits(amount):
    log = load_spending_log()
    monthly_total = log.get("monthly", {}).get(get_month_key(), 0.0)
    daily_total = log.get("daily", {}).get(get_day_key(), 0.0)
    if amount > MAX_SINGLE_TRANSFER:
        return False, f"Exceeds max single transfer: ${MAX_SINGLE_TRANSFER:.2f}"
    if daily_total + amount > DAILY_TRANSFER_LIMIT:
        return False, f"Would exceed daily limit: ${DAILY_TRANSFER_LIMIT:.2f}"
    if monthly_total + amount > MONTHLY_SPENDING_LIMIT:
        return False, f"Would exceed monthly limit: ${MONTHLY_SPENDING_LIMIT:.2f}"
    return True, "OK"

def record_spending(amount):
    log = load_spending_log()
    log["monthly"][get_month_key()] = log["monthly"].get(get_month_key(), 0.0) + amount
    log["daily"][get_day_key()] = log["daily"].get(get_day_key(), 0.0) + amount
    save_spending_log(log)

def is_destination_approved(address):
    return address.lower() in [a.lower() for a in load_approved_destinations()]

def pay_server_bill(provider, amount, destination):
    if amount <= 0:
        return {"success": False, "error": "Amount must be positive"}
    if not is_destination_approved(destination):
        return {"success": False, "error": f"Destination {destination} not in approved list"}
    allowed, msg = check_spending_limits(amount)
    if not allowed:
        return {"success": False, "error": msg}
    record_spending(amount)
    return {"success": True, "provider": provider, "amount": amount, "destination": destination, "timestamp": datetime.utcnow().isoformat()}

def get_spending_summary():
    log = load_spending_log()
    return {"daily_spent": log.get("daily", {}).get(get_day_key(), 0.0), "daily_limit": DAILY_TRANSFER_LIMIT, "monthly_spent": log.get("monthly", {}).get(get_month_key(), 0.0), "monthly_limit": MONTHLY_SPENDING_LIMIT, "max_single_transfer": MAX_SINGLE_TRANSFER}
