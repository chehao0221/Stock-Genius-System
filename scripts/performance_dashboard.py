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

LOOKBACK = 0  # 0 = 全部，>0 = 最近 N 筆

# ===============================
# Utils
# ===============================
def calc_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 自動補 hit（向下相容）
    if "hit" not in df.columns and {"pred_ret", "real_ret"}.issubset(df.columns):
        df["hit"] = (
            ((df["pred_ret"] > 0) & (df["real_ret"] > 0)) |
            ((df["pred_ret"] < 0) & (df["real_ret"] < 0))
        )

    df = df[df["real_ret"].notna()]

    if df.empty:
        return pd.DataFrame()

    if LOOKBACK > 0:
        df = df.tail(LOOKBACK)

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

    if not {"real_ret", "pred_ret"}.issubset(df.columns):
        print(f"⚠️ {label} history not settled yet, skip")
        return

    # Horizon-aware
    if "horizon" in df.columns:
        for h in sorted(df["horizon"].dropna().unique()):
            sub = df[df["horizon"] == h]
            metrics = calc_metrics(sub)
            if metrics.empty:
                continue

            metrics["market"] = label
            metrics["horizon"] = int(h)

            metrics.to_csv(
                out_path,
                mode="a",
                header=not os.path.exists(out_path),
                index=False,
            )

            print(f"✅ {label} | Horizon {h} metrics updated")
    else:
        metrics = calc_metrics(df)
        if metrics.empty:
            return

        metrics["market"] = label
        metrics["horizon"] = "NA"

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
