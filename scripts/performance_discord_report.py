import os
import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = {
    "TW": os.path.join(DATA_DIR, "metrics_tw.csv"),
    "US": os.path.join(DATA_DIR, "metrics_us.csv"),
}

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def format_block(row):
    return (
        f"Horizon：{row['horizon']} 日\n"
        f"命中率：{row['hit_rate']*100:.1f}%\n"
        f"平均報酬：{row['avg_return']*100:.2f}%\n"
        f"累積報酬：{row['cum_return']*100:.2f}%\n"
        f"最大回撤：{row['max_drawdown']*100:.2f}%"
    )


def main():
    if not WEBHOOK:
        print("❌ DISCORD_WEBHOOK_URL not set")
        return

    msg = "📊 **AI 績效 Dashboard**\n\n"

    for market, file in FILES.items():
        if not os.path.exists(file):
            continue

        df = pd.read_csv(file)
        if df.empty:
            continue

        last = df.iloc[-1]

        msg += f"**{market} 市場**\n"
        msg += "```\n" + format_block(last) + "\n```\n"

    requests.post(WEBHOOK, json={"content": msg[:1900]}, timeout=15)
    print("✅ Performance dashboard sent to Discord")


if __name__ == "__main__":
    main()
