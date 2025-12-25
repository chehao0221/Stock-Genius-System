import os, sys, datetime, requests
import pandas as pd

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.append(BASE_DIR)

CSV_FILE = os.path.join(DATA_DIR, "l4_ai_performance_history.csv")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

TZ = datetime.timezone(datetime.timedelta(hours=8))
DISCLAIMER = "📌 僅為風險與市場監控，非投資建議"

# ===============================
# Utils
# ===============================
def pct(v):
    if pd.isna(v):
        return "—"
    return f"{v:.0%}"

def delta(a, b):
    if pd.isna(a) or pd.isna(b):
        return ""
    d = b - a
    sign = "⬆️" if d > 0 else "⬇️" if d < 0 else "➡️"
    return f"{sign} {d:+.1%}"

# ===============================
# Main
# ===============================
def run():
    if not DISCORD_WEBHOOK_URL:
        return

    if not os.path.exists(CSV_FILE):
        return

    df = pd.read_csv(CSV_FILE)
    if len(df) < 2:
        return  # 至少要 2 次 L4 才有比較意義

    first = df.iloc[0]
    last = df.iloc[-1]
    n = len(df)

    embed = {
        "title": "📈 L4 黑天鵝 AI 長期表現比較",
        "description": (
            f"第 1 次 L4 ➜ 第 {n} 次 L4\n"
            f"🕒 更新時間：{datetime.datetime.now(TZ):%Y-%m-%d %H:%M}"
        ),
        "color": 0x2ECC71,
        "fields": [
            {
                "name": "🇹🇼 台股 AI",
                "value": (
                    f"樣本數：{first['tw_count']} ➜ {last['tw_count']}\n"
                    f"勝率：{pct(first['tw_win_rate'])} ➜ {pct(last['tw_win_rate'])} "
                    f"{delta(first['tw_win_rate'], last['tw_win_rate'])}"
                ),
                "inline": False,
            },
            {
                "name": "🇺🇸 美股 AI",
                "value": (
                    f"樣本數：{first['us_count']} ➜ {last['us_count']}\n"
                    f"勝率：{pct(first['us_win_rate'])} ➜ {pct(last['us_win_rate'])} "
                    f"{delta(first['us_win_rate'], last['us_win_rate'])}"
                ),
                "inline": False,
            },
            {
                "name": "🧠 系統解讀",
                "value": (
                    "• 黑天鵝期間屬極端市場，勝率非唯一指標\n"
                    "• 樣本數穩定增加代表系統持續運作\n"
                    "• 勝率趨穩代表風控邏輯成熟"
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
