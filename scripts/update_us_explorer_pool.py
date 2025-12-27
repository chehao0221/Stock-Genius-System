import os
import json
from datetime import datetime
import pandas as pd
from safe_yfinance import safe_download

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POOL_FILE = os.path.join(DATA_DIR, "explorer_pool_us.json")

# ===============================
# US Stock Universe（穩定主流版）
# ⚠️ 已涵蓋大型成交量股票，避免 API 過載
# ===============================
US_TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AMD","INTC","NFLX",
    "JPM","BAC","WFC","GS","MS","V","MA","PYPL",
    "XOM","CVX","COP",
    "JNJ","PFE","MRK","LLY",
    "KO","PEP","COST","WMT",
    "BA","CAT","GE","MMM",
    "DIS","NKE","ADBE","CRM","ORCL","IBM",
]

# ===============================
# Main
# ===============================
def run():
    print("[Explorer][US] Updating explorer pool...")

    data = safe_download(US_TICKERS, period="3mo")
    if data is None:
        print("[WARN][US] Yahoo Finance unavailable, skip update")
        return

    rows = []
    for s in US_TICKERS:
        try:
            df = data[s].dropna()
            if len(df) < 20:
                continue
            avg_vol = df["Volume"].tail(20).mean()
            rows.append({"symbol": s, "avg_volume": float(avg_vol)})
        except Exception:
            continue

    if not rows:
        print("[WARN][US] No valid volume data")
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

    print(f"[Explorer][US] Pool updated: {len(top)} symbols")

if __name__ == "__main__":
    run()
