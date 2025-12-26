import os
import json
import pandas as pd
from datetime import datetime

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

TW_HISTORY = os.path.join(DATA_DIR, "tw_history.csv")
US_HISTORY = os.path.join(DATA_DIR, "us_history.csv")

OUT_POLICY = os.path.join(DATA_DIR, "horizon_policy.json")

HORIZONS = [3, 5, 10]
MIN_TRADES = 20  # 最少樣本數，避免過擬合

# ===============================
# Utils
# ===============================
def analyze_one(df: pd.DataFrame, market: str) -> dict:
    """
    回傳每個 horizon 的表現：
    - hit_rate
    - avg_return
    - score（綜合）
    """
    result = {}

    df = df[df["real_ret"].notna()]

    if df.empty:
        return {}

    for h in HORIZONS:
        sub = df[df.get("horizon") == h]
        if len(sub) < MIN_TRADES:
            continue

        hit_rate = sub["hit"].mean()
        avg_ret = sub["real_ret"].mean()

        # 綜合分數（你之後可以改權重）
        score = hit_rate * 0.7 + avg_ret * 0.3

        result[str(h)] = {
            "trades": len(sub),
            "hit_rate": round(hit_rate, 4),
            "avg_return": round(avg_ret, 4),
            "score": round(score, 4),
        }

    return result

# ===============================
# Main
# ===============================
def run():
    policy = {
        "generated_at": datetime.now().isoformat(),
        "tw": {},
        "us": {},
    }

    if os.path.exists(TW_HISTORY):
        df_tw = pd.read_csv(TW_HISTORY)
        policy["tw"] = analyze_one(df_tw, "TW")

    if os.path.exists(US_HISTORY):
        df_us = pd.read_csv(US_HISTORY)
        policy["us"] = analyze_one(df_us, "US")

    # 選最佳 horizon
    for market in ["tw", "us"]:
        if policy[market]:
            best = max(
                policy[market].items(),
                key=lambda x: x[1]["score"],
            )
            policy[market]["best"] = best[0]

    with open(OUT_POLICY, "w") as f:
        json.dump(policy, f, indent=2)

    print("✅ Horizon policy updated")

if __name__ == "__main__":
    run()
