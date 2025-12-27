import os
import json
from datetime import datetime
import pandas as pd
from scripts.safe_yfinance import safe_download

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POOL_FILE = os.path.join(DATA_DIR, "explorer_pool_tw.json")

# ⚠️ 台股股票清單（示範版，可換成上市櫃完整清單）
TW_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2412.TW",
    "2881.TW", "2882.TW", "1301.TW", "1303.TW", "2002.TW",
]

def run():
    print("[Explorer] Updating TW explorer pool...")
    data = safe_download(TW_TICKERS, period="3mo")
    if data is None:
        print("[WARN] TW Explorer pool update skipped (data failure)")
        return

    rows = []
    for s in TW_TICKERS:
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
        "market": "TW",
        "updated_at": datetime.now().isoformat(),
        "count": len(top),
        "symbols": [r["symbol"] for r in top],
    }

    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[Explorer] TW pool updated: {len(top)} symbols")

if __name__ == "__main__":
    run()
