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
# Project Base / Data Directory
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

warnings.filterwarnings("ignore")

DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")
TZ_TW = datetime.timezone(datetime.timedelta(hours=8))

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
# Black Swan Definition
# ===============================
BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "SEC", "sanction"],
    1: ["裁員", "停產", "調查", "縮減"]
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
    if not DISCORD_WEBHOOK_URL:
        return

    now = datetime.datetime.now(TZ_TW)
    market = "TW" if now.hour < 12 else "US"
    market_open = is_market_open(market)

    cache = load_cache()
    normal, black = [], []

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

        if level == 0 and cache.get(sym) == news["title"]:
            continue

        cache[sym] = news["title"]

        embed = {
            "title": f"{sym} | {impact}",
            "url": news["link"],
            "color": 0xE74C3C if level >= 2 else 0xF1C40F,
            "fields": [
                {
                    "name": f"🚨 黑天鵝等級 L{level}" if level else "📰 焦點新聞",
                    "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                    "inline": False,
                }
            ],
        }

        (black if level else normal).append(embed)

    if normal:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": f"### 市場新聞\n📅 {now:%Y-%m-%d %H:%M}", "embeds": normal[:10]},
        )

    if black and BLACK_SWAN_WEBHOOK_URL:
        requests.post(
            BLACK_SWAN_WEBHOOK_URL,
            json={
                "content": f"🚨🚨 黑天鵝警報 🚨🚨\n📅 {now:%Y-%m-%d %H:%M}",
                "embeds": black[:10],
            },
        )

    save_cache(cache)

if __name__ == "__main__":
    run()
