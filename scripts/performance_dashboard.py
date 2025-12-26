import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import requests
from datetime import datetime

# ===============================
# Base
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

TW_HISTORY = os.path.join(DATA_DIR, "tw_history.csv")
US_HISTORY = os.path.join(DATA_DIR, "us_history.csv")

POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")
L3_FLAG = os.path.join(DATA_DIR, "l3_warning.flag")

DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# ===============================
# Config
# ===============================
CHECK_WINDOW = 20
HIT_RATE_WARN = 0.45
HIT_RATE_L3 = 0.40
L3_CONSECUTIVE_DAYS = 3

# ===============================
def load_policy():
    if not os.path.exists(POLICY_FILE):
        return {"TW": 5, "US": 5}
    return json.load(open(POLICY_FILE, "r", encoding="utf-8"))

def save_policy(p):
    json.dump(p, open(POLICY_FILE, "w", encoding="utf-8"), indent=2)

# ===============================
def calc_equity(df):
    df = df.dropna(subset=["real_ret", "hit"])
    if len(df) < CHECK_WINDOW:
        return None

    recent = df.tail(CHECK_WINDOW).copy()
    recent["equity"] = (1 + recent["real_ret"]).cumprod()
    hit_rate = recent["hit"].mean()
    return recent, hit_rate

# ===============================
def plot_equity(df, label):
    plt.figure(figsize=(6, 3))
    plt.plot(df["equity"], linewidth=2)
    plt.title(f"{label} Equity Curve（最近 {CHECK_WINDOW} 筆）")
    plt.tight_layout()

    out = os.path.join(DATA_DIR, f"equity_{label}.png")
    plt.savefig(out)
    plt.close()
    return out

# ===============================
def process_market(label, path, policy):
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path)
    result = calc_equity(df)
    if not result:
        return None

    recent, hit = result
    horizon = policy[label]
    status = "NORMAL"

    if hit < HIT_RATE_L3:
        status = "L3"
        policy[label] = max(3, horizon - 2)
    elif hit < HIT_RATE_WARN:
        policy[label] = max(3, horizon - 1)

    img = plot_equity(recent, label)

    return {
        "label": label,
        "hit": hit,
        "equity": recent["equity"].iloc[-1] - 1,
        "horizon": policy[label],
        "status": status,
        "img": img,
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

    # ---- L3 判斷 ----
    l3_count = sum(1 for r in reports if r["status"] == "L3")
    if l3_count >= L3_CONSECUTIVE_DAYS:
        open(L3_FLAG, "w").write(str(datetime.now()))

    if not DISCORD_URL or not reports:
        return

    # ===============================
    # Discord 推播
    # ===============================
    for r in reports:
        color = 0x2ECC71 if r["status"] == "NORMAL" else 0xF1C40F
        title = "🟢 系統正常" if r["status"] == "NORMAL" else "🟡 系統進入風險觀察期（L3）"

        embed = {
            "title": title,
            "description": f"{r['label']} 市場績效 Dashboard",
            "color": color,
            "fields": [
                {"name": "🎯 命中率", "value": f"{r['hit']:.2%}", "inline": True},
                {"name": "💰 累積報酬", "value": f"{r['equity']:.2%}", "inline": True},
                {"name": "⏱ Horizon", "value": f"{r['horizon']} 日", "inline": True},
            ],
            "footer": {"text": "Stock-Genius-System · 自動績效監控"},
        }

        with open(r["img"], "rb") as f:
            requests.post(
                DISCORD_URL,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"file": f},
                timeout=20,
            )

if __name__ == "__main__":
    main()
