import os
import sys
import requests
from datetime import datetime

from l4_dynamic_pause import is_system_paused
from news_radar import run_news_radar

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_TW")

def post_to_discord(message: str):
    if not DISCORD_WEBHOOK:
        raise RuntimeError("DISCORD_WEBHOOK_TW not set")

    requests.post(
        DISCORD_WEBHOOK,
        json={"content": message},
        timeout=10
    )

def main():
    # 系統暫停（L4 / L3）
    if is_system_paused():
        run_news_radar()
        return

    # 台股 AI 主流程（你原本的邏輯）
    # ↓↓↓ 不動 ↓↓↓
    # generate prediction
    # update tw_history.csv
    # build message
    message = "📊 台股 AI 分析結果（TW）"

    post_to_discord(message)

if __name__ == "__main__":
    main()
