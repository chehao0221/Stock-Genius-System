import os
import pandas as pd
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = {
    "台股": os.path.join(DATA_DIR, "metrics_tw.csv"),
    "美股": os.path.join(DATA_DIR, "metrics_us.csv"),
}

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def build_embed(market, row):
    color = 0x2ECC71 if row["hit_rate"] >= 0.5 else 0xE74C3C

    return {
        "title": f"{market}｜AI 績效 Dashboard",
        "color": color,
        "fields": [
            {
                "name": "🧠 預測週期（Horizon）",
                "value": f"{row['horizon']} 日",
                "inline": True,
            },
            {
                "name": "🎯 命中率",
                "value": f"{row['hit_rate']*100:.1f}%",
                "inline": True,
            },
            {
                "name": "📈 平均報酬",
                "value": f"{row['avg_return']*100:.2f}%",
                "inline": True,
            },
            {
                "name": "📊 累積報酬",
                "value": f"{row['cum_return']*100:.2f}%",
                "inline": True,
            },
            {
                "name": "📉 最大回撤",
                "value": f"{row['max_drawdown']*100:.2f}%",
                "inline": True,
            },
            {
                "name": "📅 更新時間",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "inline": False,
            },
        ],
        "footer": {
            "text": "Quant Intelligence System · 僅供研究參考",
        },
    }


def main():
    if not WEBHOOK:
        return

    embeds = []

    for market, file in FILES.items():
        if not os.path.exists(file):
            continue

        df = pd.read_csv(file)
        if df.empty:
            continue

        row = df.iloc[-1]
        embeds.append(build_embed(market, row))

    if embeds:
        requests.post(
            WEBHOOK,
            json={"embeds": embeds},
            timeout=15,
        )
        print("✅ 已推播 Embed 績效 Dashboard")


if __name__ == "__main__":
    main()
