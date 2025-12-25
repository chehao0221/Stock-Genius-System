import os
import sys
import yfinance as yf
import requests
import datetime
import feedparser
import urllib.parse
import pandas as pd
import json
import warnings

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

warnings.filterwarnings("ignore")

NEWS_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")
TZ_TW = datetime.timezone(datetime.timedelta(hours=8))

# ===============================
# Config: L3 → L4 Upgrade
# ===============================
L4_TIME_WINDOW_HOURS = 6      # 時間窗
L4_TRIGGER_COUNT = 2          # L3 出現次數

# ===============================
# Market Calendar
# ===============================
def is_market_open(market: str) -> bool:
    symbol = "^TWII" if market == "TW" else "^GSPC"
    try:
        df = yf.download(symbol, period="5d", progress=False)
        if df.empty:
            return False
        last_trade = df.index[-1].date()
        today = datetime.datetime.utcnow().date()
        return abs((today - last_trade).days) <= 1
    except:
        return False

# ===============================
# Black Swan Levels
# ===============================
BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "sec", "sanction"],
    1: ["裁員", "停產", "調查", "縮減"],
}

def get_black_swan_level(title: str) -> int:
    t = title.lower()
    for level, keywords in BLACK_SWAN_LEVELS.items():
        for k in keywords:
            if k.lower() in t:
                return level
    return 0

def detect_market_impact(symbol: str) -> str:
    if symbol.endswith(".TW"):
        return "🇹🇼 台股"
    if symbol.isupper():
        return "🇺🇸 美股"
    return "🌍 全球"

# ===============================
# News
# ===============================
def get_live_news(query):
    try:
        safe_query = urllib.parse.quote(query)
        url = (
            "https://news.google.com/rss/search?"
            f"q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        )
        feed = feedparser.parse(url)
        if not feed.entries:
            return None

        entry = feed.entries[0]
        pub_time = datetime.datetime(
            *entry.published_parsed[:6],
            tzinfo=datetime.timezone.utc
        )

        if (datetime.datetime.now(datetime.timezone.utc) - pub_time).total_seconds() > 43200:
            return None

        return {
            "title": entry.title.split(" - ")[0],
            "link": entry.link,
            "time": pub_time.astimezone(TZ_TW).strftime("%H:%M"),
        }
    except:
        return None

# ===============================
# Cache
# ===============================
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ===============================
# AI Symbols
# ===============================
def get_today_ai_top(market="TW"):
    file_name = "tw_history.csv" if market == "TW" else "us_history.csv"
    path = os.path.join(DATA_DIR, file_name)
    if not os.path.exists(path):
        return []

    df = pd.read_csv(path)
    latest = df["date"].max()
    return (
        df[df["date"] == latest]
        .sort_values("pred_ret", ascending=False)
        .head(5)["symbol"]
        .tolist()
    )

def get_all_ai_history(market="TW"):
    file_name = "tw_history.csv" if market == "TW" else "us_history.csv"
    path = os.path.join(DATA_DIR, file_name)
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    return sorted(df["symbol"].unique().tolist())

FIXED_WATCH = {
    "TW": ["2330.TW", "2317.TW", "2454.TW"],
    "US": ["NVDA", "AAPL", "MSFT", "TSLA"],
}

# ===============================
# Main
# ===============================
def run():
    if not NEWS_WEBHOOK_URL:
        return

    now = datetime.datetime.now(TZ_TW)
    now_ts = now.timestamp()
    market = "TW" if now.hour < 12 else "US"
    market_open = is_market_open(market)

    cache = load_cache()
    cache.setdefault("_l3_events", [])

    normal_embeds = []
    black_embeds = []

    symbols = (
        get_today_ai_top(market)
        if market_open
        else sorted(set(get_all_ai_history(market) + FIXED_WATCH.get(market, [])))
    )

    for sym in symbols:
        news = get_live_news(sym.split(".")[0])
        if not news:
            continue

        level = get_black_swan_level(news["title"])
        impact = detect_market_impact(sym)

        # 一般 cache 規則（L3 永遠不被擋）
        if level < 3 and cache.get(sym) == news["title"]:
            continue

        cache[sym] = news["title"]

        # === L3 → L4 判斷 ===
        final_level = level
        if level == 3:
            cache["_l3_events"].append(now_ts)

            # 清理時間窗外事件
            window_start = now_ts - L4_TIME_WINDOW_HOURS * 3600
            cache["_l3_events"] = [
                t for t in cache["_l3_events"] if t >= window_start
            ]

            if len(cache["_l3_events"]) >= L4_TRIGGER_COUNT:
                final_level = 4

        # === 發送邏輯 ===
        if final_level >= 3:
            name = (
                "🚨🚨 黑天鵝 L4（系統性風險）"
                if final_level == 4
                else "🚨 黑天鵝 L3"
            )

            embed = {
                "title": f"{sym} | {impact}",
                "url": news["link"],
                "color": 0x8E0000 if final_level == 4 else 0xE74C3C,
                "fields": [
                    {
                        "name": name,
                        "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                        "inline": False,
                    }
                ],
            }
            black_embeds.append(embed)
        else:
            embed = {
                "title": f"{sym} | {impact}",
                "url": news["link"],
                "color": 0x3498DB,
                "fields": [
                    {
                        "name": "📰 市場新聞",
                        "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                        "inline": False,
                    }
                ],
            }
            normal_embeds.append(embed)

    # === 推播 ===
    if normal_embeds:
        requests.post(
            NEWS_WEBHOOK_URL,
            json={
                "content": f"### 市場新聞\n📅 {now:%Y-%m-%d %H:%M}",
                "embeds": normal_embeds[:10],
            },
            timeout=15,
        )

    if black_embeds and BLACK_SWAN_WEBHOOK_URL:
        requests.post(
            BLACK_SWAN_WEBHOOK_URL,
            json={
                "content": f"🚨 黑天鵝警報\n📅 {now:%Y-%m-%d %H:%M}",
                "embeds": black_embeds[:10],
            },
            timeout=15,
        )

    save_cache(cache)

if __name__ == "__main__":
    run()
