import os
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

OBS = os.path.join(DATA_DIR, "forecast_observation.csv")

def draw(market: str, out_png: str):
    if not os.path.exists(OBS):
        return

    df = pd.read_csv(OBS)
    df = df[df["market"] == market]
    if df.empty:
        return

    df["cum"] = (1 + df["real_ret"]).cumprod()

    plt.figure(figsize=(8,4))
    plt.plot(df["cum"])
    plt.title(f"{market} Equity Curve")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

if __name__ == "__main__":
    draw("TW", os.path.join(DATA_DIR, "equity_TW.png"))
    draw("US", os.path.join(DATA_DIR, "equity_US.png"))
