import os
import json
from datetime import datetime
import pandas as pd
from scripts.safe_yfinance import safe_download

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POOL_FILE = os.path.join(DATA_DIR, "explorer_pool_us.json")

# ⚠️ 美股示範池（之後可換成 Russell / NASDAQ 全表）
US_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "AMD", "INTC", "NFLX", "BAC", "JPM", "XOM", "CVX",
]

def run():
    print("[Explorer] Updating US explorer pool...")
    data = safe_download(US_TICKERS, period="3mo")
    if data is None:
        print("[WARN] US Explorer pool update skipped (data failure)")
        return

    rows = []
    for s in US_TICKERS:
        try:
            df = data[s].dropna()
            if len(df) < 20:
                continue
            avg_vol = df["Volume"].tail(20).mean()
            rows.append({"symbol": s, "avg_volume": avg_vol})
        except Exception:
            continue

    if not rows:
        return

    top = sorted(rows, key=lambda x: x["avg_volume"], reverse=True)[:500]

    payload = {
        "market": "US",
        "updated_at": datetime.now().isoformat(),
        "count": len(top),
        "symbols": [r["symbol"] for r in top],
    }

    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[Explorer] US pool updated: {len(top)} symbols")

if __name__ == "__main__":
    run()
