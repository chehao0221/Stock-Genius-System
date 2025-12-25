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
import csv

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
L4_ACTIVE_FILE = os.getenv("L4_ACTIVE_FILE", "data/l4_active.flag")

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")
BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")

TZ_TW = datetime.timezone(datetime.timedelta(hours=8))

# ===============================
# Config
# ===============================
L4_TIME_WINDOW_HOURS = 6
L4_TRIGGER_COUNT = 2
L4_NEWS_PAUSE_HOURS = 24

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
    for level, keys in BLACK_SWAN_LEVELS.items():
        for k in keys:
            if k.lower() in t:
                return level
    return 0

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
# CSV Logger
# ===============================
def log_black_swan(level, symbol, market, title, link):
    exists = os.path.exists(BLACK_SWAN_CSV)
    with open(BLACK_SWAN_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["datetime", "level", "symbol", "market", "title", "link"])
        writer.writerow([
            datetime.datetime.now(TZ_TW).strftime("%Y-%m-%d %H:%M"),
            level,
            symbol,
            market,
            title,
            link
        ])

# ===============================
# Helpers from AI history
# ===============================
def get_today_ai_top(market="TW"):
    file = "tw_history.csv" if market == "TW" else "us_history.csv"
    path = os.path.join(DATA_DIR, file)
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

# ===============================
# Main
# ===============================
def run():
    now = datetime.datetime.now(TZ_TW)
    now_ts = now.timestamp()

    cache = load_cache()
    cache.setdefault("_l3_events", [])
    cache.setdefault("_l4_pause_until", 0)

    # ===============================
    # L4 AUTO RECOVER
    # ===============================
    if os.path.exists(L4_ACTIVE_FILE) and now_ts > cache["_l4_pause_until"]:
        os.remove(L4_ACTIVE_FILE)

        if BLACK_SWAN_WEBHOOK_URL:
            requests.post(
                BLACK_SWAN_WEBHOOK_URL,
                json={
                    "content": (
                        "📊 **L4 黑天鵝事件回顧（自動）**\n"
                        f"🕒 結束時間：{now:%Y-%m-%d %H:%M}\n"
                        "✅ 系統已解除 L4 狀態\n"
                        "▶️ AI 分析已自動恢復"
                    )
                },
                timeout=15,
            )

    market = "TW" if now.hour < 12 else "US"
    market_open = is_market_open(market)

    symbols = get_today_ai_top(market) if market_open else []

    normal_embeds = []
    black_embeds = []

    for sym in symbols:
        news = get_live_news(sym.split(".")[0])
        if not news:
            continue

        level = get_black_swan_level(news["title"])

        if level < 3 and cache.get(sym) == news["title"]:
            continue

        cache[sym] = news["title"]
        final_level = level

        if level == 3:
            cache["_l3_events"].append(now_ts)
            window = now_ts - L4_TIME_WINDOW_HOURS * 3600
            cache["_l3_events"] = [t for t in cache["_l3_events"] if t >= window]

            if len(cache["_l3_events"]) >= L4_TRIGGER_COUNT:
                final_level = 4
                cache["_l4_pause_until"] = now_ts + L4_NEWS_PAUSE_HOURS * 3600

                with open(L4_ACTIVE_FILE, "w") as f:
                    f.write(str(now_ts))

        if final_level >= 3:
            embed = {
                "title": "GLOBAL | 系統性黑天鵝" if final_level == 4 else f"{sym} | 黑天鵝",
                "url": news["link"],
                "color": 0x8E0000 if final_level == 4 else 0xE74C3C,
                "fields": [
                    {
                        "name": "🚨🚨 黑天鵝 L4（系統性風險）"
                        if final_level == 4
                        else "🚨 黑天鵝 L3",
                        "value": (
                            f"[{news['title']}]({news['link']})\n"
                            f"🕒 {news['time']}\n"
                            "📍 狀態：L4 active（AI 已凍結）"
                            if final_level == 4
                            else f"[{news['title']}]({news['link']})\n🕒 {news['time']}"
                        ),
                        "inline": False,
                    }
                ],
            }
            black_embeds.append(embed)
            log_black_swan(final_level, sym, market, news["title"], news["link"])

        else:
            if now_ts < cache["_l4_pause_until"]:
                continue

            normal_embeds.append({
                "title": f"{sym} | 市場新聞",
                "url": news["link"],
                "color": 0x3498DB,
                "fields": [
                    {
                        "name": "📰 市場新聞",
                        "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                        "inline": False,
                    }
                ],
            })

    if normal_embeds and NEWS_WEBHOOK_URL:
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
