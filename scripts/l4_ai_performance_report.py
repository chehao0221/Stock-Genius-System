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
    if df.empty:
        return None

    df = df.copy()
    df["actual_ret"] = (
        df.groupby("symbol")["entry_price"]
        .pct_change()
        .shift(-5)
    )

    df = df.dropna(subset=["actual_ret"])

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

# ===============================
# Main
# ===============================
def run():
    if not DISCORD_WEBHOOK_URL:
        return

    if not os.path.exists(OBS_FLAG_FILE):
        return

    l4_end_ts = float(open(OBS_FLAG_FILE).read())
    l4_end = datetime.datetime.fromtimestamp(l4_end_ts, TZ)

    now = datetime.datetime.now(TZ)

    tw = load_history("tw_history.csv")
    us = load_history("us_history.csv")

    tw_m = calc_metrics(tw)
    us_m = calc_metrics(us)

    msg = (
        "📊 **L4 黑天鵝 AI 表現回顧報告**\n"
        f"🕒 產生時間：{now:%Y-%m-%d %H:%M}\n\n"
    )

    if tw_m:
        msg += (
            "🇹🇼 **台股 AI**\n"
            f"- 筆數：{tw_m['count']}\n"
            f"- 勝率：{tw_m['win_rate']:.0%}\n"
            f"- 平均報酬：{tw_m['avg_ret']:+.2%}\n"
            f"- 最大回撤：{tw_m['max_dd']:+.2%}\n\n"
        )

    if us_m:
        msg += (
            "🇺🇸 **美股 AI**\n"
            f"- 筆數：{us_m['count']}\n"
            f"- 勝率：{us_m['win_rate']:.0%}\n"
            f"- 平均報酬：{us_m['avg_ret']:+.2%}\n"
            f"- 最大回撤：{us_m['max_dd']:+.2%}\n\n"
        )

    msg += (
        "🧠 **系統結論**\n"
        "- AI 在高風險期間以防守為主\n"
        "- 波動放大時，預測誤差增加屬正常\n\n"
        f"{DISCLAIMER}"
    )

    requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": msg[:1900]},
        timeout=15,
    )

if __name__ == "__main__":
    run()
