import os
import json
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")
SNAPSHOT_FILE = os.path.join(DATA_DIR, ".horizon_policy_last.json")

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def main():
    if not WEBHOOK or not os.path.exists(POLICY_FILE):
        return

    current = json.load(open(POLICY_FILE, "r", encoding="utf-8"))

    if os.path.exists(SNAPSHOT_FILE):
        prev = json.load(open(SNAPSHOT_FILE, "r", encoding="utf-8"))
    else:
        prev = {}

    changes = []
    for k, v in current.items():
        if prev.get(k) != v:
            changes.append((k, prev.get(k), v))

    if changes:
        msg = "🚨 **Horizon 策略調整通知**\n\n"
        for m, old, new in changes:
            msg += f"- {m.upper()}：{old} → **{new} 日**\n"

        requests.post(WEBHOOK, json={"content": msg}, timeout=15)

    json.dump(current, open(SNAPSHOT_FILE, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
