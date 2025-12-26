import os
import json
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_US")

HORIZON_PATH = os.path.join(DATA_DIR, "horizon_policy.json")
L3_FLAG = os.path.join(DATA_DIR, "l3_warning.flag")

def load_horizon():
    try:
        with open(HORIZON_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("current_horizon", "5D")
    except:
        return "5D"

def load_data():
    return [
        {"symbol": "AAPL", "pred": 2.07, "support": 265.03, "resist": 286.7},
        {"symbol": "NVDA", "pred": 1.56, "support": 176.79, "resist": 198.77},
        {"symbol": "TSLA", "pred": 7.66, "support": 434.08, "resist": 510.79},
        {"symbol": "MSFT", "pred": -2.06, "support": 474.27, "resist": 496.89},
        {"symbol": "GOOGL", "pred": 1.08, "support": 297.65, "resist": 328.16},
        {"symbol": "AMZN", "pred": -0.75, "support": 222.7, "resist": 240.68},
        {"symbol": "META", "pred": 0.14, "support": 629.47, "resist": 704.91},
    ]

def emoji_pred(v):
    return "📈" if v > 0 else "📉"

def medal(rank):
    return ["🥇", "🥈", "🥉"][rank] if rank < 3 else ""

def post():
    data = load_data()
    horizon = load_horizon()
    risk = "🟡 系統進入風險觀察期 (L3)" if os.path.exists(L3_FLAG) else "🟢 系統正常運作"

    sorted_data = sorted(data, key=lambda x: x["pred"], reverse=True)

    fields = []
    for i, d in enumerate(sorted_data):
        fields.append({
            "name": f"{medal(i)} {d['symbol']}",
            "value": (
                f"{emoji_pred(d['pred'])} 預估 {d['pred']:+.2f}%\n"
                f"支撐 {d['support']} / 壓力 {d['resist']}"
            ),
            "inline": True
        })

    embed = {
        "title": "📊 美股 AI 5 日預測報告",
        "description": f"📅 {datetime.now().date()}\n{risk}\n🧭 Horizon：{horizon}",
        "color": 0x3498DB,
        "fields": fields,
        "footer": {
            "text": "模型為機率推估，僅供研究參考，非投資建議。"
        }
    }

    requests.post(WEBHOOK, json={"embeds": [embed]})

if __name__ == "__main__":
    post()
