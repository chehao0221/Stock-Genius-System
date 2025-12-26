import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

OBS = os.path.join(DATA_DIR, "forecast_observation.csv")

def snapshot(market: str, window=7):
    if not os.path.exists(OBS):
        return None

    df = pd.read_csv(OBS)
    df = df[df["market"] == market].tail(window)
    if df.empty:
        return None

    return {
        "hit_rate": round(df["hit"].mean(), 3),
        "avg_ret": round(df["real_ret"].mean(), 4),
        "count": len(df),
    }

if __name__ == "__main__":
    print("TW:", snapshot("TW"))
    print("US:", snapshot("US"))
