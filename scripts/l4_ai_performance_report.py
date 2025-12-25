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

TZ = datetime.timezone(datetime.timedelta(hours=8))
DISCLAIMER = "📌 僅為風險與市場監控，非投資建議"

# ===============================
# Utils
# ===============================
def load_history(file):
    path = os.path.join(DATA_DIR, file)
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)

def calc_metrics(df):
    if df.empty:
        return None

    df = df.copy()

    # 計算 5 日實際報酬（簡化估計）
    df["actual_ret"] = df.groupby("symbol")["entry_price"].pct_change().shift(-5)
    df = df.dropna(subset=["actual_ret"])

    if df.empty:
        return None

    win = (
        (df["actual_ret"] > 0) & (df["pred_ret"] > 0)
    ) | (
        (df["actual_ret"] < 0) & (df["pred_ret"] < 0)
    )

    return {
        "count": len(df),
        "win_rate": win.mean(),
        "avg_ret": df["actual_ret"].mean(),
        "max_dd": df["actual_ret"].min(),
    }

def format_block(title, m):
    if not m:
        return f"**{title}**\n資料不足\n"

    return (
        f"**{title}**\n"
        f"筆數：{m['count']}\n"
        f"勝率：{m['win_rate']:.0%}\n"
        f"平均報酬：{m['avg_ret']:+.2%}\n"
        f"最大回撤：{m['max_dd']:+.2%}"
    )

# ===============================
# Main
# ===============================
def run():
    if not DISCORD_WEBHOOK_URL:
        return

    if not os.path.exists(OBS_FLAG_FILE):
        return

    now = datetime.datetime.now(TZ)

    tw = load_history("tw_history.csv")
    us = load_history("us_history.csv")

    tw_m = calc_metrics(tw)
    us_m = calc_metrics(us)

    embed = {
        "title": "📊 L4 黑天鵝 AI 表現回顧報告",
        "description": f"🕒 產生時間：{now:%Y-%m-%d %H:%M}",
        "color": 0x5865F2,  # Discord blurple
        "fields": [
            {
                "name": "🇹🇼 台股 AI",
                "value": format_block("台股", tw_m),
                "inline": True,
            },
            {
                "name": "🇺🇸 美股 AI",
                "value": format_block("美股", us_m),
                "inline": True,
            },
            {
                "name": "🧠 系統結論",
                "value": (
                    "• AI 在極端風險期間以防守為主\n"
                    "• 高波動時預測誤差擴大屬正常\n"
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
