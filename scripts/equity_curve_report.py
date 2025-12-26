import os
import pandas as pd
import matplotlib.pyplot as plt
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = {
    "台股": os.path.join(DATA_DIR, "tw_history.csv"),
    "美股": os.path.join(DATA_DIR, "us_history.csv"),
}

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def plot_equity(df, title, path):
    df = df.dropna(subset=["real_ret"])
    if df.empty:
        return False

    df["權益曲線"] = (1 + df["real_ret"]).cumprod()

    plt.figure(figsize=(6, 4))
    plt.plot(df["權益曲線"])
    plt.title(title)
    plt.xlabel("交易序列")
    plt.ylabel("資金變化")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return True


def main():
    if not WEBHOOK:
        return

    for market, file in FILES.items():
        if not os.path.exists(file):
            continue

        df = pd.read_csv(file)
        img = os.path.join(DATA_DIR, f"equity_{market}.png")

        if not plot_equity(df, f"{market}｜AI 權益曲線", img):
            continue

        embed = {
            "title": f"📈 {market}｜AI 權益曲線",
            "color": 0x3498DB,
            "footer": {
                "text": "Equity Curve · 累積報酬視覺化",
            },
        }

        with open(img, "rb") as f:
            requests.post(
                WEBHOOK,
                data={"payload_json": str({"embeds": [embed]}).replace("'", '"')},
                files={"file": f},
                timeout=30,
            )

    print("✅ 已推播 Equity Curve（Embed）")


if __name__ == "__main__":
    main()
