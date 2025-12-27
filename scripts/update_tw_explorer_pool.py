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

POOL_FILE = os.path.join(DATA_DIR, "explorer_pool_tw.json")

# ===============================
# TW Stock Universe（簡化穩定版）
# ⚠️ 若你之後要全上市櫃，可換成完整清單
# ===============================
TW_TICKERS = [
    "2330.TW","2317.TW","2454.TW","2308.TW","2412.TW","2881.TW","2882.TW",
    "1301.TW","1303.TW","2002.TW","1216.TW","1101.TW","1102.TW","2603.TW",
    "2609.TW","2615.TW","3037.TW","3711.TW","5871.TW","5880.TW",
]

# ===============================
# Main
# ===============================
def run():
    print("[Explorer][TW] Updating explorer pool...")

    data = safe_download(TW_TICKERS, period="3mo")
    if data is None:
        print("[WARN][TW] Yahoo Finance unavailable, skip update")
        return

    rows = []
    for s in TW_TICKERS:
        try:
            df = data[s].dropna()
            if len(df) < 20:
                continue
            avg_vol = df["Volume"].tail(20).mean()
            rows.append({"symbol": s, "avg_volume": float(avg_vol)})
        except Exception:
            continue

    if not rows:
        print("[WARN][TW] No valid volume data")
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

    print(f"[Explorer][TW] Pool updated: {len(top)} symbols")

if __name__ == "__main__":
    run()
