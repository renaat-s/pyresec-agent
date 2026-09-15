import json
import os
from datetime import datetime

AUDIT_LOG_FILE = "audit_log.jsonl"

def log_event(event_type, details, severity="INFO"):
    entry = {"timestamp": datetime.utcnow().isoformat(), "event_type": event_type, "severity": severity, "details": details}
    with open(AUDIT_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def log_transaction(tx_type, amount, destination, status, tx_hash=None):
    log_event("TRANSACTION", {"type": tx_type, "amount": amount, "destination": destination, "status": status, "tx_hash": tx_hash})

def log_api_call(endpoint, method, status_code, client_ip=None):
    log_event("API_CALL", {"endpoint": endpoint, "method": method, "status_code": status_code, "client_ip": client_ip})

def log_audit_scan(file_hash, result_summary, cost):
    log_event("AUDIT_SCAN", {"file_hash": file_hash, "result_summary": result_summary, "cost": cost})

def log_kill_switch(triggered_by, reason):
    log_event("KILL_SWITCH", {"triggered_by": triggered_by, "reason": reason}, severity="CRITICAL")

def log_heartbeat(balance, status):
    log_event("HEARTBEAT", {"balance": balance, "status": status})

def log_replication(amount, dev_cut):
    log_event("REPLICATION", {"surplus_amount": amount, "dev_cut": dev_cut})

def get_recent_logs(n=50):
    if not os.path.exists(AUDIT_LOG_FILE):
        return []
    logs = []
    with open(AUDIT_LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return logs[-n:]
