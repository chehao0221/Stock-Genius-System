import json, os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(BASE_DIR, "data", "horizon_policy.json")

COOLDOWN_DAYS = 5

def run():
    with open(POLICY, "r") as f:
        policy = json.load(f)

    today = datetime.utcnow().date()
    changed = False

    for mkt, cfg in policy.items():
        last = datetime.fromisoformat(cfg.get("last_change", "2000-01-01")).date()
        if (today - last).days < COOLDOWN_DAYS:
            continue

        if cfg.get("hit_rate", 1) < cfg.get("min_hit_rate", 0.45):
            cfg["current"] = max(3, cfg["current"] - 2)
            cfg["last_change"] = today.isoformat()
            changed = True

    if changed:
        with open(POLICY, "w") as f:
            json.dump(policy, f, indent=2)

if __name__ == "__main__":
    run()
