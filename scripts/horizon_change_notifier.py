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
    prev = json.load(open(SNAPSHOT_FILE, "r", encoding="utf-8")) if os.path.exists(SNAPSHOT_FILE) else {}

    changes = []
    for market, new_h in current.items():
        old_h = prev.get(market)
        if old_h != new_h:
            changes.append((market.upper(), old_h, new_h))

    if changes:
        msg = "🚨 **預測週期（Horizon）自動調整通知**\n\n"
        for m, old, new in changes:
            if old is None:
                msg += f"- {m}：啟用 **{new} 日預測週期**\n"
            else:
                msg += f"- {m}：由 {old} 日 → **{new} 日**\n"

        msg += "\n📌 原因：近期命中率下降，系統自動進行風險保守調整"
        requests.post(WEBHOOK, json={"content": msg[:1900]}, timeout=15)

    json.dump(current, open(SNAPSHOT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
