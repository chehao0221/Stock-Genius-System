import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "data", "system_state.json")

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"mode": "NORMAL"}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state: dict):
    state["last_update"] = datetime.utcnow().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_mode():
    return load_state().get("mode", "NORMAL")
