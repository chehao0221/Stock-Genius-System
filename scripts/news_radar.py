import os, sys, json, csv, warnings, datetime, requests, feedparser, urllib.parse
import yfinance as yf
import pandas as pd

# ===============================
# Base / Env
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

NEWS_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()
L4_ACTIVE_FILE = os.getenv("L4_ACTIVE_FILE", os.path.join(DATA_DIR, "l4_active.flag"))
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")
BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")

TZ = datetime.timezone(datetime.timedelta(hours=8))
warnings.filterwarnings("ignore")

# ===============================
# Config
# ===============================
L4_TIME_WINDOW_HOURS = 6
L4_TRIGGER_COUNT = 2
L4_NEWS_PAUSE_HOURS = 24
OBSERVATION_HOURS = 24

BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "sec", "sanction"],
    1: ["裁員", "停產", "調查"],
}

# ===============================
# Helpers
# ===============================
def now():
    return datetime.datetime.now(TZ)

def ts():
    return now().timestamp()

def load_cache():
    if os.path.exists(CACHE_FILE):
        return json.load(open(CACHE_FILE, encoding="utf-8"))
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def get_black_swan_level(title):
    t = title.lower()
    for lv, keys in BLACK_SWAN_LEVELS.items():
        if any(k.lower() in t for k in keys):
            return lv
    return 0

def get_news(query):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
    feed = feedparser.parse(url)
    if not feed.entries:
        return None
    e = feed.entries[0]
    return {
        "title": e.title.split(" - ")[0],
        "link": e.link,
        "time": datetime.datetime(*e.published_parsed[:6], tzinfo=datetime.timezone.utc).astimezone(TZ).strftime("%H:%M")
    }

def log_black_swan(level, symbol, title, link):
    exists = os.path.exists(BLACK_SWAN_CSV)
    with open(BLACK_SWAN_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["datetime", "level", "symbol", "title", "link"])
        w.writerow([now().strftime("%Y-%m-%d %H:%M"), level, symbol, title, link])

def in_observation():
    if not os.path.exists(OBS_FLAG_FILE):
        return False
    try:
        return (ts() - float(open(OBS_FLAG_FILE).read())) < OBSERVATION_HOURS * 3600
    except:
        return False

# ===============================
# Main
# ===============================
def run():
    cache = load_cache()
    cache.setdefault("_l3_ts", [])
    cache.setdefault("_l4_until", 0)
    cache.setdefault("_l4_events", [])

    current_ts = ts()
    mode = "🟢 NORMAL"
    if os.path.exists(L4_ACTIVE_FILE):
        mode = "🔴 L4 ACTIVE"
    elif in_observation():
        mode = "🟠 OBSERVATION"

    # 🔁 L4 auto recover
    if os.path.exists(L4_ACTIVE_FILE) and current_ts > cache["_l4_until"]:
        os.remove(L4_ACTIVE_FILE)
        open(OBS_FLAG_FILE, "w").write(str(current_ts))

        # 📊 Post-Mortem
        summary = "\n".join(
            f"• {e['symbol']}｜{e['title']}"
            for e in cache["_l4_events"]
        ) or "（無事件）"

        if BLACK_SWAN_WEBHOOK_URL:
            requests.post(BLACK_SWAN_WEBHOOK_URL, json={
                "content":
                f"📊 **L4 黑天鵝結束回顧**\n"
                f"🕒 {now():%Y-%m-%d %H:%M}\n\n"
                f"{summary}\n\n"
                f"➡️ 系統進入 OBSERVATION"
            })

        cache["_l4_events"] = []

    # 讀取 AI 最新標的
    symbols = []
    for f in ["tw_history.csv", "us_history.csv"]:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            df = pd.read_csv(p)
            symbols += df[df["date"] == df["date"].max()]["symbol"].tolist()

    normal, black = [], []

    for s in set(symbols):
        news = get_news(s.split(".")[0])
        if not news:
            continue

        level = get_black_swan_level(news["title"])
        final = level

        if level == 3:
            cache["_l3_ts"].append(current_ts)
            cache["_l3_ts"] = [t for t in cache["_l3_ts"] if current_ts - t <= L4_TIME_WINDOW_HOURS * 3600]

            if len(cache["_l3_ts"]) >= L4_TRIGGER_COUNT:
                final = 4
                cache["_l4_until"] = current_ts + L4_NEWS_PAUSE_HOURS * 3600
                open(L4_ACTIVE_FILE, "w").write(str(current_ts))

        if final >= 3:
            cache["_l4_events"].append({"symbol": s, "title": news["title"]})
            log_black_swan(final, s, news["title"], news["link"])

            black.append({
                "title": f"{s} | 黑天鵝 L{final}",
                "url": news["link"],
                "color": 0x8E0000,
                "fields": [{
                    "name": f"🚨 黑天鵝 L{final}",
                    "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                    "inline": False
                }]
            })

        elif current_ts > cache["_l4_until"]:
            normal.append({
                "title": f"{s} | 市場新聞",
                "url": news["link"],
                "color": 0x3498DB,
                "fields": [{
                    "name": "📰 新聞",
                    "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                    "inline": False
                }]
            })

    if normal and NEWS_WEBHOOK_URL:
        requests.post(NEWS_WEBHOOK_URL, json={
            "content": f"{mode}｜📰 市場新聞 {now():%H:%M}",
            "embeds": normal[:10]
        })

    if black and BLACK_SWAN_WEBHOOK_URL:
        requests.post(BLACK_SWAN_WEBHOOK_URL, json={
            "content": f"{mode}｜🚨 黑天鵝警報",
            "embeds": black[:10]
        })

    save_cache(cache)

if __name__ == "__main__":
    run()
