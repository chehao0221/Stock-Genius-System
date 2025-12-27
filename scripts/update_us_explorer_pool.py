import os
import json
import pandas as pd
from datetime import datetime
from scripts.safe_yfinance import safe_download

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POOL_FILE = os.path.join(DATA_DIR, "us_explorer_pool.json")

# 你可自行調整來源（S&P500 已經很夠）
US_UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","JPM","V",
    # 👉 實務上可擴充到 1000+，這裡示意
]

def main():
    df = safe_download(US_UNIVERSE, period="3mo")
    if df is None:
        print("[WARN] Skip US explorer pool update")
        return

    vols = []
    for s in US_UNIVERSE:
        try:
            v = df[s]["Volume"].tail(20).mean()
            vols.append((s, float(v)))
        except Exception:
            continue

    if len(vols) < 50:
        print("[WARN] Not enough US symbols, keep old pool")
        return

    top = sorted(vols, key=lambda x: x[1], reverse=True)[:500]

    payload = {
        "updated_at": datetime.utcnow().isoformat(),
        "symbols": [s for s, _ in top],
    }

    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] US explorer pool updated: {len(payload['symbols'])} symbols")

if __name__ == "__main__":
    main()
