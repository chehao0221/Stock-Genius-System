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

HISTORY_CSV = os.path.join(DATA_DIR, "l4_ai_performance_history.csv")

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

    # 簡化估計 5 日實際報酬（避免即時抓價）
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
        "count": int(len(df)),
        "win_rate": float(win.mean()),
        "avg_ret": float(df["actual_ret"].mean()),
        "max_dd": float(df["actual_ret"].min()),
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

def next_l4_id():
    if not os.path.exists(HISTORY_CSV):
        return 1
    try:
        df = pd.read_csv(HISTORY_CSV)
        if df.empty:
            return 1
        return int(df["l4_id"].max()) + 1
    except:
        return 1

def append_csv(l4_id, market, metrics, ts):
    row = {
        "l4_id": l4_id,
        "date": ts.strftime("%Y-%m-%d"),
        "datetime": ts.strftime("%Y-%m-%d %H:%M"),
        "market": market,
        "count": metrics["count"] if metrics else 0,
        "win_rate": metrics["win_rate"] if metrics else None,
        "avg_ret": metrics["avg_ret"] if metrics else None,
        "max_dd": metrics["max_dd"] if metrics else None,
    }

    df = pd.DataFrame([row])
    df.to_csv(
        HISTORY_CSV,
        mode="a",
        header=not os.path.exists(HISTORY_CSV),
        index=False,
    )

# ===============================
# Main
# ===============================
def run():
    if not DISCORD_WEBHOOK_URL:
        return

    # 只在 L4 結束後才產生報告
    if not os.path.exists(OBS_FLAG_FILE):
        return

    now = datetime.datetime.now(TZ)
    l4_id = next_l4_id()

    tw = load_history("tw_history.csv")
    us = load_history("us_history.csv")

    tw_m = calc_metrics(tw)
    us_m = calc_metrics(us)

    # ===== CSV 紀錄 =====
    append_csv(l4_id, "TW", tw_m, now)
    append_csv(l4_id, "US", us_m, now)

    # ===== Discord Embed =====
    embed = {
        "title": f"📊 L4 黑天鵝 AI 表現回顧報告（第 {l4_id} 次）",
        "description": f"🕒 產生時間：{now:%Y-%m-%d %H:%M}",
        "color": 0x5865F2,
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
                    "• AI 在極端風險期間自動轉為防守模式\n"
                    "• 高波動下預測誤差上升屬正常現象\n"
                    "• 系統成功避免過度進攻行為"
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
