import os
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta

# ===============================
# Path / Config
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "l4_market_impact.csv")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

MARKET_INDEX = {
    "TW": "^TWII",
    "US": "^GSPC"
}

WINDOWS = [0, 1, 3, 5, 10]

# ===============================
# Utilities
# ===============================
def get_price(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    if df.empty:
        return None
    return df["Close"]

def calc_returns(series, base_date):
    if base_date not in series.index:
        return {}

    base_price = series.loc[base_date]
    result = {}

    for d in WINDOWS:
        try:
            target_date = base_date + timedelta(days=d)
            future = series[series.index >= target_date].iloc[0]
            result[f"ret_{d}d"] = round((future / base_price - 1) * 100, 2)
        except Exception:
            result[f"ret_{d}d"] = None

    return result

# ===============================
# Main
# ===============================
def run():
    if not os.path.exists(BLACK_SWAN_CSV):
        print("❌ black_swan_history.csv not found")
        return

    df = pd.read_csv(BLACK_SWAN_CSV)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date

    records = []

    for _, row in df.iterrows():
        market = row.get("market", "TW")
        index = MARKET_INDEX.get(market)

        if not index:
            continue

        event_date = row["date"]
        start = event_date - timedelta(days=3)
        end = event_date + timedelta(days=15)

        price = get_price(index, start, end)
        if price is None:
            continue

        returns = calc_returns(price, pd.to_datetime(event_date))

        record = {
            "date": event_date,
            "market": market,
            "symbol": row["symbol"],
            "level": row["level"],
            "title": row["title"],
            "index": index,
        }
        record.update(returns)
        records.append(record)

    if not records:
        print("⚠️ No valid L4 events")
        return

    out = pd.DataFrame(records)
    out.to_csv(OUTPUT_CSV, index=False)

    # ===============================
    # Discord Summary
    # ===============================
    if DISCORD_WEBHOOK_URL:
        l4 = out[out["level"] == 4]
        if not l4.empty:
            avg = l4[[c for c in out.columns if c.startswith("ret_")]].mean()
            msg = (
                "📊 **L4 事件 × 市場影響統計**\n\n"
                f"樣本數：{len(l4)}\n"
                f"T+1 日：{avg['ret_1d']:.2f}%\n"
                f"T+3 日：{avg['ret_3d']:.2f}%\n"
                f"T+5 日：{avg['ret_5d']:.2f}%\n"
                f"T+10 日：{avg['ret_10d']:.2f}%\n\n"
                "（來源：歷史黑天鵝事件）"
            )
            requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": msg},
                timeout=15
            )

    print(f"✅ L4 market impact saved → {OUTPUT_CSV}")

# ===============================
if __name__ == "__main__":
    run()
