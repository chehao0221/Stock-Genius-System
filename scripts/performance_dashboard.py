import os
import pandas as pd
from datetime import datetime

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

TW_HISTORY = os.path.join(DATA_DIR, "tw_history.csv")
US_HISTORY = os.path.join(DATA_DIR, "us_history.csv")

OUT_TW = os.path.join(DATA_DIR, "metrics_tw.csv")
OUT_US = os.path.join(DATA_DIR, "metrics_us.csv")

# ===============================
# Utils
# ===============================
def calc_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算：
    - total trades
    - hit rate
    - avg return
    - cumulative return
    - max drawdown
    """
    df = df.copy()
    df = df[df["real_ret"].notna()]

    if df.empty:
        return pd.DataFrame()

    df["cum_ret"] = (1 + df["real_ret"]).cumprod() - 1
    peak = df["cum_ret"].cummax()
    df["drawdown"] = df["cum_ret"] - peak

    metrics = {
        "date": datetime.now().date(),
        "trades": len(df),
        "hit_rate": round(df["hit"].mean(), 4),
        "avg_return": round(df["real_ret"].mean(), 4),
        "cum_return": round(df["cum_ret"].iloc[-1], 4),
        "max_drawdown": round(df["drawdown"].min(), 4),
    }

    return pd.DataFrame([metrics])

# ===============================
# Main
# ===============================
def run_one(history_path: str, out_path: str, label: str):
    if not os.path.exists(history_path):
        print(f"⚠️ {label} history not found, skip")
        return

    df = pd.read_csv(history_path)

    required = {"real_ret", "hit"}
    if not required.issubset(df.columns):
        print(f"⚠️ {label} history not settled yet, skip")
        return

    metrics = calc_metrics(df)
    if metrics.empty:
        print(f"⚠️ {label} no settled trades")
        return

    metrics["market"] = label

    metrics.to_csv(
        out_path,
        mode="a",
        header=not os.path.exists(out_path),
        index=False,
    )

    print(f"✅ {label} metrics updated")

def main():
    run_one(TW_HISTORY, OUT_TW, "TW")
    run_one(US_HISTORY, OUT_US, "US")

if __name__ == "__main__":
    main()
