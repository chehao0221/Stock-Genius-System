import os
import json
import requests
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_TW")

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
        {"symbol": "2454.TW", "pred": 2.34, "support": 1346.7, "resist": 1441.7},
        {"symbol": "0050.TW", "pred": 0.66, "support": 62.5, "resist": 65.7},
        {"symbol": "2330.TW", "pred": 0.11, "support": 1438.5, "resist": 1548.2},
        {"symbol": "2317.TW", "pred": -0.31, "support": 213.8, "resist": 236.8},
        {"symbol": "2308.TW", "pred": -4.11, "support": 893.0, "resist": 1012.0},
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
        "title": "📊 台股 AI 5 日預測報告",
        "description": f"📅 {datetime.now().date()}\n{risk}\n🧭 Horizon：{horizon}",
        "color": 0x2ECC71,
        "fields": fields,
        "footer": {
            "text": "模型為機率推估，僅供研究參考，非投資建議。"
        }
    }

    requests.post(WEBHOOK, json={"embeds": [embed]})

if __name__ == "__main__":
    post()
