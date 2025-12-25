import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
L4_ACTIVE_FILE = os.getenv("L4_ACTIVE_FILE", os.path.join(DATA_DIR, "l4_active.flag"))

ASSETS = {
    "BIL": "💵 現金 / 短債",
    "TLT": "🛡️ 長天期美債",
    "GLD": "🥇 黃金",
    "VIXY": "🌪️ 波動率",
    "SPY": "📉 大盤對照"
}

REPORT_FILE = os.path.join(DATA_DIR, "l4_defense_report.csv")

def run():
    if not os.path.exists(L4_ACTIVE_FILE):
        return

    prices = yf.download(
        list(ASSETS.keys()),
        period="30d",
        auto_adjust=True,
        progress=False
    )["Close"]

    returns = (prices.iloc[-1] / prices.iloc[0] - 1).sort_values(ascending=False)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Discord message
    msg = f"🛡️ **L4 防禦模式啟動**\n🕒 {now}\n\n"
    msg += "📊 **近 30 日防禦資產表現**\n"

    for s, r in returns.items():
        msg += f"{ASSETS[s]} `{s}`：`{r:+.2%}`\n"

    msg += "\n⚠️ 系統已暫停進攻型 AI\n"
    msg += "➡️ 建議維持防禦資產，等待 L4 結束"

    if DISCORD_WEBHOOK_URL:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": msg},
            timeout=15
        )

    # Save record
    df = pd.DataFrame({
        "datetime": [now],
        **{f"{k}_30d_ret": [v] for k, v in returns.items()}
    })
    df.to_csv(
        REPORT_FILE,
        mode="a",
        header=not os.path.exists(REPORT_FILE),
        index=False
    )

if __name__ == "__main__":
    run()
