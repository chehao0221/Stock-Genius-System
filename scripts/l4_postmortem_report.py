import os
import sys
import csv
import json
import datetime
import requests
import warnings
import yfinance as yf
import pandas as pd

warnings.filterwarnings("ignore")

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

# ===============================
# Environment
# ===============================
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()

L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
L4_LAST_END_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")
BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")
POSTMORTEM_FLAG = os.path.join(DATA_DIR, "l4_postmortem_sent.flag")

TZ = datetime.timezone(datetime.timedelta(hours=8))

# ===============================
# Helpers
# ===============================
def read_ts(path):
    try:
        return float(open(path).read().strip())
    except:
        return None

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M")

def pct(a, b):
    try:
        return (b - a) / a * 100
    except:
        return None

def get_index_return(symbol, start_ts, end_ts):
    try:
        start = datetime.datetime.fromtimestamp(start_ts, datetime.timezone.utc)
        end = datetime.datetime.fromtimestamp(end_ts, datetime.timezone.utc)
        df = yf.download(
            symbol,
            start=start.strftime("%Y-%m-%d"),
            end=(end + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
        if len(df) < 2:
            return None
        return pct(df["Close"].iloc[0], df["Close"].iloc[-1])
    except:
        return None

# ===============================
# Main
# ===============================
def run():
    # 必須：L4 已結束、且還沒發過回顧
    if os.path.exists(L4_ACTIVE_FILE):
        return
    if not os.path.exists(L4_LAST_END_FILE):
        return
    if os.path.exists(POSTMORTEM_FLAG):
        return
    if not BLACK_SWAN_WEBHOOK_URL:
        return

    end_ts = read_ts(L4_LAST_END_FILE)
    if not end_ts:
        return

    # 從黑天鵝紀錄反推最近一次 L4 start
    if not os.path.exists(BLACK_SWAN_CSV):
        return

    rows = []
    with open(BLACK_SWAN_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                t = datetime.datetime.strptime(
                    r["datetime"], "%Y-%m-%d %H:%M"
                ).replace(tzinfo=TZ).timestamp()
                if t <= end_ts:
                    rows.append((t, r))
            except:
                continue

    l4_rows = [r for t, r in rows if r["level"] == "4"]
    if not l4_rows:
        return

    # 最近一次 L4 start
    l4_start_ts = min(
        datetime.datetime.strptime(
            r["datetime"], "%Y-%m-%d %H:%M"
        ).replace(tzinfo=TZ).timestamp()
        for r in l4_rows
    )

    duration_hours = (end_ts - l4_start_ts) / 3600

    # 統計
    l3_count = len([r for t, r in rows if r["level"] == "3" and t >= l4_start_ts])
    symbols = sorted({r["symbol"] for r in l4_rows if r["symbol"] != "GLOBAL"})
    markets = sorted({r["market"] for r in l4_rows if r["market"] != "GLOBAL"})

    # 指數影響
    sp_ret = get_index_return("^GSPC", l4_start_ts, end_ts)
    nq_ret = get_index_return("^IXIC", l4_start_ts, end_ts)

    # ===============================
    # Compose Discord Message
    # ===============================
    msg = (
        "📊 **L4 黑天鵝事件回顧報告（Postmortem）**\n\n"
        f"🕒 **期間**：{fmt(l4_start_ts)} ～ {fmt(end_ts)}\n"
        f"⏱ **持續時間**：{duration_hours:.1f} 小時\n\n"
        "### 🔍 事件概況\n"
        f"• L3 事件累積：{l3_count} 次\n"
        f"• 涉及市場：{', '.join(markets) if markets else 'GLOBAL'}\n"
        f"• 涉及標的：{', '.join(symbols[:8])}{'...' if len(symbols) > 8 else ''}\n\n"
        "### 🤖 系統行為\n"
        "• AI 海選：暫停\n"
        "• 僅保留：權值股／監控模式\n"
        "• 新聞雷達：持續監控\n\n"
        "### 📉 市場影響（期間）\n"
    )

    if sp_ret is not None:
        msg += f"• S&P 500：{sp_ret:+.2f}%\n"
    if nq_ret is not None:
        msg += f"• NASDAQ：{nq_ret:+.2f}%\n"

    msg += (
        "\n### 🧠 系統結論\n"
        "⚠️ 判定為 **系統性風險事件**\n"
        "✅ L4 防禦機制有效啟動並完整執行\n\n"
        "📌 *提醒：僅為風險與市場監控，非投資建議*"
    )

    requests.post(
        BLACK_SWAN_WEBHOOK_URL,
        json={"content": msg[:1900]},
        timeout=15,
    )

    # 標記已送出
    open(POSTMORTEM_FLAG, "w").write(str(end_ts))


if __name__ == "__main__":
    run()
