import os, sys, json, csv, warnings, datetime, requests, feedparser, urllib.parse
import yfinance as yf
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

NEWS_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()
L4_ACTIVE_FILE = os.getenv("L4_ACTIVE_FILE", "data/l4_active.flag")
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")
BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")

TZ = datetime.timezone(datetime.timedelta(hours=8))
warnings.filterwarnings("ignore")

L4_TIME_WINDOW_HOURS = 6
L4_TRIGGER_COUNT = 2
L4_NEWS_PAUSE_HOURS = 24

BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "sec", "sanction"],
    1: ["裁員", "停產", "調查"],
}

def get_black_swan_level(title):
    t = title.lower()
    for lv, keys in BLACK_SWAN_LEVELS.items():
        if any(k.lower() in t for k in keys):
            return lv
    return 0

def load_cache():
    return json.load(open(CACHE_FILE)) if os.path.exists(CACHE_FILE) else {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w"), ensure_ascii=False, indent=2)

def get_news(q):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
    feed = feedparser.parse(url)
    if not feed.entries:
        return None
    e = feed.entries[0]
    return {
        "title": e.title.split(" - ")[0],
        "link": e.link,
        "time": datetime.datetime(*e.published_parsed[:6], tzinfo=datetime.timezone.utc).astimezone(TZ).strftime("%H:%M")
    }

def run():
    now = datetime.datetime.now(TZ)
    ts = now.timestamp()
    cache = load_cache()
    cache.setdefault("_l3", [])
    cache.setdefault("_pause_until", 0)

    # 🔁 L4 auto recover
    if os.path.exists(L4_ACTIVE_FILE) and ts > cache["_pause_until"]:
        os.remove(L4_ACTIVE_FILE)
        open(OBS_FLAG_FILE, "w").write(str(ts))
        if BLACK_SWAN_WEBHOOK_URL:
            requests.post(BLACK_SWAN_WEBHOOK_URL, json={
                "content": f"📊 **L4 黑天鵝結束回顧**\n🕒 {now:%Y-%m-%d %H:%M}\n▶️ AI 已恢復"
            })

    symbols = []
    for f in ["tw_history.csv", "us_history.csv"]:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            df = pd.read_csv(p)
            symbols += df[df["date"] == df["date"].max()]["symbol"].tolist()

    normal, black = [], []

    for s in set(symbols):
        n = get_news(s.split(".")[0])
        if not n:
            continue

        lv = get_black_swan_level(n["title"])
        final = lv

        if lv == 3:
            cache["_l3"].append(ts)
            cache["_l3"] = [t for t in cache["_l3"] if ts - t <= L4_TIME_WINDOW_HOURS * 3600]
            if len(cache["_l3"]) >= L4_TRIGGER_COUNT:
                final = 4
                cache["_pause_until"] = ts + L4_NEWS_PAUSE_HOURS * 3600
                open(L4_ACTIVE_FILE, "w").write(str(ts))

        if final >= 3:
            black.append({
                "title": f"{s} | 黑天鵝 L{final}",
                "url": n["link"],
                "color": 0x8E0000,
                "fields": [{
                    "name": f"🚨 黑天鵝 L{final}",
                    "value": f"[{n['title']}]({n['link']})\n🕒 {n['time']}\n📍 L4 active" if final == 4 else f"[{n['title']}]({n['link']})",
                    "inline": False
                }]
            })
        elif ts > cache["_pause_until"]:
            normal.append({
                "title": f"{s} | 市場新聞",
                "url": n["link"],
                "color": 0x3498DB,
                "fields": [{
                    "name": "📰 新聞",
                    "value": f"[{n['title']}]({n['link']})\n🕒 {n['time']}",
                    "inline": False
                }]
            })

    if normal and NEWS_WEBHOOK_URL:
        requests.post(NEWS_WEBHOOK_URL, json={"content": f"📰 市場新聞 {now:%H:%M}", "embeds": normal[:10]})
    if black and BLACK_SWAN_WEBHOOK_URL:
        requests.post(BLACK_SWAN_WEBHOOK_URL, json={"content": f"🚨 黑天鵝警報", "embeds": black[:10]})

    save_cache(cache)

if __name__ == "__main__":
    run()
