import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")

DEFAULT = {"TW": 5, "US": 5}

if not os.path.exists(POLICY_FILE):
    json.dump(DEFAULT, open(POLICY_FILE, "w", encoding="utf-8"), indent=2)
