import os, sys, datetime, requests
import pandas as pd

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

# ===============================
# Env
# ===============================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")
HISTORY_FILE = os.path.join(DATA_DIR, "l4_ai_performance_history.csv")

TZ = datetime.timezone(datetime.timedelta(hours=8))
DISCLAIMER = "📌 提醒：僅為風險與市場監控，非投資建議"

# ===============================
# Utils
# ===============================
def load_history(file):
    path = os.path.join(DATA_DIR, file)
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)

def calc_metrics(df):
    if df.empty or "actual_ret" not in df.columns:
        return None

    win = (
        (df["actual_ret"] > 0) & (df["pred_ret"] > 0)
    ) | (
        (df["actual_ret"] < 0) & (df["pred_ret"] < 0)
    )

    return {
        "count": len(df),
        "win_rate": round(win.mean(), 3),
        "avg_ret": round(df["actual_ret"].mean(), 4),
    }

def next_l4_id():
    if not os.path.exists(HISTORY_FILE):
        return 1
    df = pd.read_csv(HISTORY_FILE)
    return int(df["l4_id"].max()) + 1

# ===============================
# Main
# ===============================
def run():
    if not DISCORD_WEBHOOK_URL:
        return

    # 必須是 L4 剛結束
    if os.path.exists(L4_ACTIVE_FILE) or not os.path.exists(OBS_FLAG_FILE):
        return

    end_ts = float(open(OBS_FLAG_FILE).read().strip())
    end_time = datetime.datetime.fromtimestamp(end_ts, TZ)

    # 嘗試找 L4 起始時間
    start_ts = end_ts - 24 * 3600
    start_time = datetime.datetime.fromtimestamp(start_ts, TZ)
    duration_hours = round((end_ts - start_ts) / 3600, 1)

    tw = load_history("tw_history.csv")
    us = load_history("us_history.csv")

    tw_m = calc_metrics(tw)
    us_m = calc_metrics(us)

    l4_id = next_l4_id()

    # ===============================
    # Save CSV
    # ===============================
    row = {
        "l4_id": l4_id,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        "duration_hours": duration_hours,
        "tw_win_rate": tw_m["win_rate"] if tw_m else None,
        "us_win_rate": us_m["win_rate"] if us_m else None,
        "tw_avg_ret": tw_m["avg_ret"] if tw_m else None,
        "us_avg_ret": us_m["avg_ret"] if us_m else None,
        "notes": "Auto generated",
    }

    pd.DataFrame([row]).to_csv(
        HISTORY_FILE,
        mode="a",
        header=not os.path.exists(HISTORY_FILE),
        index=False,
    )

    # ===============================
    # Discord Report
    # ===============================
    embed = {
        "title": f"📊 L4 事件回顧報告（第 {l4_id} 次）",
        "description": (
            f"🕒 結束時間：{end_time:%Y-%m-%d %H:%M}\n"
            f"⏱ 持續：約 {duration_hours} 小時"
        ),
        "color": 0x5865F2,
        "fields": [
            {
                "name": "🇹🇼 台股 AI",
                "value": (
                    f"勝率：{tw_m['win_rate']:.0%}\n"
                    f"平均報酬：{tw_m['avg_ret']:+.2%}"
                    if tw_m else "資料不足"
                ),
                "inline": True,
            },
            {
                "name": "🇺🇸 美股 AI",
                "value": (
                    f"勝率：{us_m['win_rate']:.0%}\n"
                    f"平均報酬：{us_m['avg_ret']:+.2%}"
                    if us_m else "資料不足"
                ),
                "inline": True,
            },
            {
                "name": "⚠️ 風險聲明",
                "value": DISCLAIMER,
                "inline": False,
            },
        ],
    }

    requests.post(
        DISCORD_WEBHOOK_URL,
        json={"embeds": [embed]},
        timeout=15,
    )

if __name__ == "__main__":
    run()
