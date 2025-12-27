import os
import json
from datetime import datetime
from scripts.safe_yfinance import safe_download

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POOL_FILE = os.path.join(DATA_DIR, "us_explorer_pool.json")

# ⚠️ 來源池（示範版）
# 真正實務你之後可換成 Russell 3000 / NASDAQ All
US_UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","JPM","V",
    "AVGO","COST","AMD","NFLX","CRM","INTC","CSCO","QCOM","TXN","ORCL",
]

def main():
    print("[INFO] Updating US explorer pool...")

    df = safe_download(US_UNIVERSE, period="3mo")
    if df is None:
        print("[WARN] Yahoo unavailable, keep old US pool")
        return

    vols = []
    for s in US_UNIVERSE:
        try:
            v = float(df[s]["Volume"].tail(20).mean())
            vols.append((s, v))
        except Exception:
            continue

    if len(vols) < 10:
        print("[WARN] Insufficient US data, skip update")
        return

    top = sorted(vols, key=lambda x: x[1], reverse=True)[:500]

    payload = {
        "market": "US",
        "updated_at": datetime.utcnow().isoformat(),
        "symbols": [s for s, _ in top],
    }

    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] US explorer pool updated ({len(payload['symbols'])} symbols)")

if __name__ == "__main__":
    main()
