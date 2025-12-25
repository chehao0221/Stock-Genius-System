import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

COMPARE_FILE = os.path.join(DATA_DIR, "l4_ai_performance_compare.csv")
POLICY_FILE = os.path.join(DATA_DIR, "l4_pause_policy.json")

DEFAULT_POLICY = {
    "pause_hours": 24,
    "reason": "default"
}

def decide_pause_hours(row):
    sim = row["simulated_ai_return_if_continue"]

    if sim is None:
        return 24, "no_data"

    if sim < -0.03:
        return 48, "severe_drawdown"
    elif sim < -0.01:
        return 24, "moderate_risk"
    else:
        return 12, "low_impact"

def run():
    if not os.path.exists(COMPARE_FILE):
        print("No comparison data, keep default")
        json.dump(DEFAULT_POLICY, open(POLICY_FILE, "w"), indent=2)
        return

    df = pd.read_csv(COMPARE_FILE)

    if df.empty:
        json.dump(DEFAULT_POLICY, open(POLICY_FILE, "w"), indent=2)
        return

    # 取最近一次 L4
    latest = df.iloc[-1]
    hours, reason = decide_pause_hours(latest)

    policy = {
        "pause_hours": hours,
        "reason": reason,
        "based_on_l4": latest["l4_datetime"]
    }

    json.dump(policy, open(POLICY_FILE, "w"), indent=2)
    print("✅ L4 pause policy updated:", policy)

if __name__ == "__main__":
    run()
