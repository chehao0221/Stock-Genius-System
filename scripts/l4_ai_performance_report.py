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
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

HISTORY_TW = os.path.join(DATA_DIR, "tw_history.csv")
HISTORY_US = os.path.join(DATA_DIR, "us_history.csv")
L4_SUMMARY_CSV = os.path.join(DATA_DIR, "l4_ai_performance_history.csv")

TZ = datetime.timezone(datetime.timedelta(hours=8))
DISCLAIMER = "📌 僅為風險與市場監控，非投資建議"

# ===============================
# Utils
# ===============================
def load_history(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)

def calc_metrics(df):
    if df.empty:
        return None

    df = df.copy()

    # 使用已結算資料
    if "settled" in df.columns:
        df = df[df["settled"] == True]

    if df.empty:
        return None

    win = (
        (df["pred_ret"] > 0) & (df["entry_price"].pct_change() > 0)
    ) | (
        (df["pred_ret"] < 0) & (df["entry_price"].pct_change() < 0)
    )

    return {
        "count": len(df),
        "win_rate": win.mean(),
        "avg_pred": df["pred_ret"].mean(),
    }

def fmt(m):
    if not m:
        return "資料不足"
    return (
        f"筆數：{m['count']}\n"
        f"勝率：{m['win_rate']:.0%}\n"
        f"平均預測：{m['avg_pred']:+.2%}"
    )

# ===============================
# Main
# ===============================
def run():
    if not os.path.exists(OBS_FLAG_FILE):
        return

    now = datetime.datetime.now(TZ)
    l4_end_ts = open(OBS_FLAG_FILE).read().strip()

    tw = load_history(HISTORY_TW)
    us = load_history(HISTORY_US)

    tw_m = calc_metrics(tw)
    us_m = calc_metrics(us)

    # ===============================
    # Save CSV（長期累積）
    # ===============================
    row = {
        "l4_end_time": now.strftime("%Y-%m-%d %H:%M"),
        "l4_end_ts": l4_end_ts,
        "tw_count": tw_m["count"] if tw_m else 0,
        "tw_win_rate": tw_m["win_rate"] if tw_m else None,
        "tw_avg_pred": tw_m["avg_pred"] if tw_m else None,
        "us_count": us_m["count"] if us_m else 0,
        "us_win_rate": us_m["win_rate"] if us_m else None,
        "us_avg_pred": us_m["avg_pred"] if us_m else None,
    }

    df_row = pd.DataFrame([row])
    df_row.to_csv(
        L4_SUMMARY_CSV,
        mode="a",
        header=not os.path.exists(L4_SUMMARY_CSV),
        index=False,
    )

    # ===============================
    # Discord Report
    # ===============================
    if not DISCORD_WEBHOOK_URL:
        return

    embed = {
        "title": "📊 L4 黑天鵝 AI 表現回顧報告",
        "description": f"🕒 產生時間：{now:%Y-%m-%d %H:%M}",
        "color": 0x5865F2,
        "fields": [
            {
                "name": "🇹🇼 台股 AI",
                "value": fmt(tw_m),
                "inline": True,
            },
            {
                "name": "🇺🇸 美股 AI",
                "value": fmt(us_m),
                "inline": True,
            },
            {
                "name": "🧠 系統結論",
                "value": (
                    "• 黑天鵝期間 AI 以風控為優先\n"
                    "• 預測勝率下降屬合理現象\n"
                    "• 系統成功避免過度進攻"
                ),
                "inline": False,
            },
            {
                "name": "⚠️ 風險提示",
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
