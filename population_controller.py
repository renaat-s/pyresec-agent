import os
import json
from datetime import datetime

MAX_ACTIVE_AGENTS = int(os.getenv("MAX_ACTIVE_AGENTS", "5"))
REGISTRY_FILE = "agent_registry.json"
KILL_SWITCH_FILE = "kill_switch.json"

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    return {"agents": {}, "created_count": 0}

def save_registry(registry):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)

def register_agent(agent_id, metadata=None):
    registry = load_registry()
    if len(registry["agents"]) >= MAX_ACTIVE_AGENTS:
        return {"success": False, "error": f"Population cap: {len(registry['agents'])}/{MAX_ACTIVE_AGENTS}"}
    registry["agents"][agent_id] = {"registered_at": datetime.utcnow().isoformat(), "status": "active", "metadata": metadata or {}}
    registry["created_count"] = registry.get("created_count", 0) + 1
    save_registry(registry)
    return {"success": True, "agent_id": agent_id, "active_count": len(registry["agents"]), "max_allowed": MAX_ACTIVE_AGENTS}

def deregister_agent(agent_id):
    registry = load_registry()
    if agent_id not in registry["agents"]:
        return {"success": False, "error": f"Agent {agent_id} not found"}
    registry["agents"][agent_id]["status"] = "terminated"
    registry["agents"][agent_id]["terminated_at"] = datetime.utcnow().isoformat()
    save_registry(registry)
    return {"success": True, "agent_id": agent_id, "active_count": len([a for a in registry["agents"].values() if a["status"] == "active"])}

def get_population_status():
    registry = load_registry()
    active = len([a for a in registry["agents"].values() if a["status"] == "active"])
    return {"active_count": active, "max_allowed": MAX_ACTIVE_AGENTS, "remaining_capacity": MAX_ACTIVE_AGENTS - active, "total_created": registry.get("created_count", 0)}

def is_kill_switch_active():
    if os.path.exists(KILL_SWITCH_FILE):
        with open(KILL_SWITCH_FILE, "r") as f:
            return json.load(f).get("active", False)
    return False

def trigger_kill_switch(triggered_by, reason):
    data = {"active": True, "triggered_by": triggered_by, "reason": reason, "triggered_at": datetime.utcnow().isoformat()}
    with open(KILL_SWITCH_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data

def reset_kill_switch():
    data = {"active": False, "reset_at": datetime.utcnow().isoformat()}
    with open(KILL_SWITCH_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data
