import os
import json
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")
SNAPSHOT_FILE = os.path.join(DATA_DIR, ".horizon_policy_last.json")

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def main():
    if not WEBHOOK or not os.path.exists(POLICY_FILE):
        return

    current = json.load(open(POLICY_FILE, "r", encoding="utf-8"))
    prev = json.load(open(SNAPSHOT_FILE, "r", encoding="utf-8")) if os.path.exists(SNAPSHOT_FILE) else {}

    fields = []
    for market, new_h in current.items():
        old_h = prev.get(market)
        if old_h != new_h:
            if old_h is None:
                value = f"啟用 **{new_h} 日預測週期**"
            else:
                value = f"{old_h} 日 → **{new_h} 日**"

            fields.append({
                "name": market.upper(),
                "value": value,
                "inline": True,
            })

    if fields:
        embed = {
            "title": "🚨 預測週期（Horizon）自動調整通知",
            "color": 0xF1C40F,
            "fields": fields,
            "footer": {
                "text": "系統因命中率惡化自動進行風險保守調整",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=15)

    json.dump(current, open(SNAPSHOT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
