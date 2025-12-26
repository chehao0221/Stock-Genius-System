import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

METRICS = {
    "tw": os.path.join(DATA_DIR, "metrics_tw.csv"),
    "us": os.path.join(DATA_DIR, "metrics_us.csv"),
}

POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")

# 🔧 風控參數（可自行調）
HIT_THRESHOLD = 0.5      # 命中率 < 50%
MIN_TRADES = 20          # 最少樣本
STEP_DOWN = 1            # 每次降 1 日
MIN_HORIZON = 3          # 最低 Horizon


def main():
    if not os.path.exists(POLICY_FILE):
        print("❌ horizon_policy.json not found")
        return

    policy = json.load(open(POLICY_FILE, "r", encoding="utf-8"))
    updated = False

    for market, file in METRICS.items():
        if not os.path.exists(file):
            continue

        df = pd.read_csv(file)
        if df.empty:
            continue

        last = df.iloc[-1]

        if last["trades"] < MIN_TRADES:
            continue

        if last["hit_rate"] < HIT_THRESHOLD:
            current = int(policy.get(market, 5))
            new_h = max(MIN_HORIZON, current - STEP_DOWN)

            if new_h < current:
                policy[market] = new_h
                updated = True
                print(
                    f"🚨 {market.upper()} 命中率 {last['hit_rate']*100:.1f}% "
                    f"→ Horizon {current} → {new_h}"
                )

    if updated:
        with open(POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump(policy, f, indent=2, ensure_ascii=False)

        print("✅ Horizon policy updated")
    else:
        print("🟢 Horizon stable, no action")


if __name__ == "__main__":
    main()
