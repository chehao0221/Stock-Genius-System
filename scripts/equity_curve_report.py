import os
import pandas as pd
import matplotlib.pyplot as plt
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = {
    "TW": os.path.join(DATA_DIR, "tw_history.csv"),
    "US": os.path.join(DATA_DIR, "us_history.csv"),
}

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def plot_equity(df, title, path):
    df = df.dropna(subset=["real_ret"])
    if df.empty:
        return False

    df["equity"] = (1 + df["real_ret"]).cumprod()

    plt.figure(figsize=(6, 4))
    plt.plot(df["equity"])
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return True


def send_image(path, title):
    with open(path, "rb") as f:
        requests.post(
            WEBHOOK,
            files={"file": (os.path.basename(path), f)},
            data={"content": title},
            timeout=30,
        )


def main():
    if not WEBHOOK:
        return

    for market, file in FILES.items():
        if not os.path.exists(file):
            continue

        df = pd.read_csv(file)
        img = os.path.join(DATA_DIR, f"equity_{market}.png")

        if plot_equity(df, f"{market} Equity Curve", img):
            send_image(img, f"📈 **{market} Equity Curve**")


if __name__ == "__main__":
    main()
