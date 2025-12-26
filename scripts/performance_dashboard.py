import os
import json
import pandas as pd
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

TW_HISTORY = os.path.join(DATA_DIR, "tw_history.csv")
US_HISTORY = os.path.join(DATA_DIR, "us_history.csv")
POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")

DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# ===============================
# Config
# ===============================
HIT_RATE_WARN = 0.45
HIT_RATE_L3 = 0.40
CHECK_WINDOW = 20

# ===============================
def calc_metrics(df: pd.DataFrame):
    df = df.dropna(subset=["real_ret", "hit"])
    if len(df) < CHECK_WINDOW:
        return None

    recent = df.tail(CHECK_WINDOW)
    hit_rate = recent["hit"].mean()
    avg_ret = recent["real_ret"].mean()
    cum_ret = (1 + recent["real_ret"]).prod() - 1

    return hit_rate, avg_ret, cum_ret

# ===============================
def load_policy():
    if not os.path.exists(POLICY_FILE):
        return {"TW": 5, "US": 5}
    return json.load(open(POLICY_FILE, "r", encoding="utf-8"))

def save_policy(policy):
    json.dump(policy, open(POLICY_FILE, "w", encoding="utf-8"), indent=2)

# ===============================
def process_market(label, path, policy):
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path)
    metrics = calc_metrics(df)
    if not metrics:
        return None

    hit, avg, cum = metrics
    horizon = policy[label]

    status = "NORMAL"
    if hit < HIT_RATE_L3:
        status = "L3"
        policy[label] = max(3, horizon - 2)
    elif hit < HIT_RATE_WARN:
        policy[label] = max(3, horizon - 1)

    return {
        "market": label,
        "hit": hit,
        "avg": avg,
        "cum": cum,
        "horizon": policy[label],
        "status": status,
    }

# ===============================
def main():
    policy = load_policy()
    reports = []

    for label, path in [("TW", TW_HISTORY), ("US", US_HISTORY)]:
        r = process_market(label, path, policy)
        if r:
            reports.append(r)

    save_policy(policy)

    if not DISCORD_URL or not reports:
        return

    fields = []
    color = 0x2ECC71

    for r in reports:
        if r["status"] == "L3":
            color = 0xF1C40F

        fields.append({
            "name": f"{r['market']} 市場",
            "value": (
                f"🎯 命中率：`{r['hit']:.2%}`\n"
                f"📈 平均報酬：`{r['avg']:.2%}`\n"
                f"💰 累積報酬：`{r['cum']:.2%}`\n"
                f"⏱ Horizon：`{r['horizon']} 日`"
            ),
            "inline": True
        })

    embed = {
        "title": "📊 AI 績效 Dashboard",
        "description": f"最近 {CHECK_WINDOW} 筆交易統計",
        "color": color,
        "fields": fields,
        "footer": {"text": "Stock-Genius-System · 自動績效監控"}
    }

    requests.post(DISCORD_URL, json={"embeds": [embed]}, timeout=15)

if __name__ == "__main__":
    main()
