import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "data", "system_state.json")

DEFAULT_STATE = {
    "mode": "NORMAL",
    "since": datetime.utcnow().isoformat(),
    "last_update": None,
    "locked_by": None
}

def load_state():
    if not os.path.exists(STATE_FILE):
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state: dict):
    state["last_update"] = datetime.utcnow().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_mode() -> str:
    return load_state().get("mode", "NORMAL")
