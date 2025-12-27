import os
import json
from datetime import datetime
from scripts.safe_yfinance import safe_download

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POOL_FILE = os.path.join(DATA_DIR, "tw_explorer_pool.json")

# ⚠️ 台股示範池（之後可換上市櫃完整清單）
TW_UNIVERSE = [
    "2330.TW","2317.TW","2454.TW","2308.TW","2881.TW","2882.TW",
    "1301.TW","1303.TW","2002.TW","1216.TW",
    "2603.TW","2615.TW","3037.TW","3231.TW","3661.TW",
]

def main():
    print("[INFO] Updating TW explorer pool...")

    df = safe_download(TW_UNIVERSE, period="3mo")
    if df is None:
        print("[WARN] Yahoo unavailable, keep old TW pool")
        return

    vols = []
    for s in TW_UNIVERSE:
        try:
            v = float(df[s]["Volume"].tail(20).mean())
            vols.append((s, v))
        except Exception:
            continue

    if len(vols) < 10:
        print("[WARN] Insufficient TW data, skip update")
        return

    top = sorted(vols, key=lambda x: x[1], reverse=True)[:500]

    payload = {
        "market": "TW",
        "updated_at": datetime.utcnow().isoformat(),
        "symbols": [s for s, _ in top],
    }

    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] TW explorer pool updated ({len(payload['symbols'])} symbols)")

if __name__ == "__main__":
    main()
