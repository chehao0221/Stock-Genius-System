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

# ===============================
# Basic Settings
# ===============================
warnings.filterwarnings("ignore")

DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
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
# Black Swan
# ===============================
BLACK_SWAN_KEYWORDS = [
    "破產", "違約", "下市", "調查", "制裁",
    "停產", "爆炸", "裁員", "倒閉",
    "SEC", "lawsuit", "bankruptcy", "halt"
]

def is_black_swan(title: str) -> bool:
    t = title.lower()
    return any(k.lower() in t for k in BLACK_SWAN_KEYWORDS)

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
        pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        if (now_utc - pub_time).total_seconds() / 3600 > 12:
            return None

        return {
            "title": entry.title.split(" - ")[0],
            "link": entry.link,
            "time": pub_time.astimezone(TZ_TW).strftime("%H:%M")
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

# ===============================
# Fixed Watch
# ===============================
FIXED_WATCH = {
    "TW": ["2330.TW", "2317.TW", "2454.TW"],
    "US": ["NVDA", "AAPL", "MSFT", "TSLA"]
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

    news_cache = load_cache()
    embeds = []

    # ===============================
    # Watch List Decision
    # ===============================
    if market_open:
        symbols = get_today_ai_top(market)
        label = "AI 海選強勢股"
        title = "📈 AI 交易日雷達"
    else:
        symbols = sorted(set(get_all_ai_history(market) + FIXED_WATCH.get(market, [])))
        label = "假日關注股"
        title = "🟡 假日市場觀察"

    # ===============================
    # News Loop
    # ===============================
    for sym in symbols:
        try:
            search_key = sym.split(".")[0]
            news = get_live_news(search_key)
            if not news:
                continue

            force_push = is_black_swan(news["title"])

            if not force_push and news_cache.get(sym) == news["title"]:
                continue

            news_cache[sym] = news["title"]

            embed = {
                "title": f"{sym} | {label}",
                "url": news["link"],
                "color": 0xE74C3C if force_push else 0x3498DB,
                "fields": [
                    {
                        "name": "📰 焦點新聞",
                        "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                        "inline": False,
                    }
                ],
                "footer": {
                    "text": "🚨 黑天鵝警報"
                    if force_push
                    else "Quant Master News Radar"
                },
            }

            embeds.append(embed)

        except:
            continue

    if not embeds:
        return

    header = title
    if any(is_black_swan(e["fields"][0]["value"]) for e in embeds):
        header = "🚨 黑天鵝即時警報"

    requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": f"### {header}\n📅 {now:%Y-%m-%d %H:%M}", "embeds": embeds[:10]},
        timeout=15,
    )

    save_cache(news_cache)

if __name__ == "__main__":
    run()
