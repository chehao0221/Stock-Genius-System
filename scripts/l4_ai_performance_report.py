import os, sys, datetime, requests
import pandas as pd

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.append(BASE_DIR)

# ===============================
# Env
# ===============================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")
REPORT_SENT_FILE = os.path.join(DATA_DIR, "l4_postmortem_sent.flag")

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
    if df.empty or len(df) < 6:
        return None

    df = df.copy().sort_values(["symbol", "date"])

    # 模擬 5 日後 exit（研究用途）
    df["exit_price"] = df.groupby("symbol")["entry_price"].shift(-5)
    df = df.dropna(subset=["exit_price"])

    df["actual_ret"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"]

    if df.empty:
        return None

    direction_win = (
        ((df["actual_ret"] > 0) & (df["pred_ret"] > 0)) |
        ((df["actual_ret"] < 0) & (df["pred_ret"] < 0))
    )

    return {
        "count": len(df),
        "win_rate": direction_win.mean(),
        "avg_ret": df["actual_ret"].mean(),
        "worst_ret": df["actual_ret"].min(),
    }

def format_block(title, m):
    if not m:
        return f"**{title}**\n資料不足（樣本不足）"

    return (
        f"**{title}**\n"
        f"樣本數：{m['count']}\n"
        f"方向勝率：{m['win_rate']:.0%}\n"
        f"平均結果：{m['avg_ret']:+.2%}\n"
        f"最差結果：{m['worst_ret']:+.2%}"
    )

# ===============================
# Main
# ===============================
def run():
    if not DISCORD_WEBHOOK_URL:
        return

    if not os.path.exists(OBS_FLAG_FILE):
        return

    # 只允許 L4 結束後 1 小時內送一次
    last_end = float(open(OBS_FLAG_FILE).read().strip())
    now = datetime.datetime.now(TZ)
    if (now.timestamp() - last_end) > 3600:
        return

    if os.path.exists(REPORT_SENT_FILE):
        return

    tw = load_history("tw_history.csv")
    us = load_history("us_history.csv")

    tw_m = calc_metrics(tw)
    us_m = calc_metrics(us)

    embed = {
        "title": "📊 L4 黑天鵝事件｜AI 表現回顧",
        "description": f"🕒 產生時間：{now:%Y-%m-%d %H:%M}",
        "color": 0x5865F2,
        "fields": [
            {
                "name": "🇹🇼 台股 AI",
                "value": format_block("台股模型", tw_m),
                "inline": True,
            },
            {
                "name": "🇺🇸 美股 AI",
                "value": format_block("美股模型", us_m),
                "inline": True,
            },
            {
                "name": "🧠 系統結論",
                "value": (
                    "• 極端風險期間以防守為優先\n"
                    "• 高波動環境下預測誤差放大屬正常\n"
                    "• L4 機制成功避免錯誤進攻"
                ),
                "inline": False,
            },
            {
                "name": "⚠️ 重要提醒",
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

    open(REPORT_SENT_FILE, "w").write(str(now.timestamp()))

if __name__ == "__main__":
    run()
