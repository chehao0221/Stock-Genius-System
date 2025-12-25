import os, sys, json, csv, warnings, datetime, requests, feedparser, urllib.parse
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

L4_ACTIVE_FILE = os.getenv(
    "L4_ACTIVE_FILE",
    os.path.join(DATA_DIR, "l4_active.flag")
)
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

# ===============================
# Black Swan Keywords
# ===============================
BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "sec", "sanction"],
    1: ["裁員", "停產", "調查"],
}

def get_black_swan_level(title: str) -> int:
    t = title.lower()
    for lv, keys in BLACK_SWAN_LEVELS.items():
        if any(k.lower() in t for k in keys):
            return lv
    return 0

# ===============================
# Cache
# ===============================
def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        return json.load(open(CACHE_FILE, encoding="utf-8"))
    except:
        return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ===============================
# News Fetch
# ===============================
def get_news(query):
    url = (
        "https://news.google.com/rss/search?"
        f"q={urllib.parse.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
    )
    feed = feedparser.parse(url)
    if not feed.entries:
        return None

    e = feed.entries[0]
    pub = datetime.datetime(
        *e.published_parsed[:6],
        tzinfo=datetime.timezone.utc
    )

    if (datetime.datetime.now(datetime.timezone.utc) - pub).total_seconds() > 12 * 3600:
        return None

    return {
        "title": e.title.split(" - ")[0],
        "link": e.link,
        "time": pub.astimezone(TZ).strftime("%H:%M"),
    }

# ===============================
# CSV Log
# ===============================
def log_black_swan(level, symbol, title, link):
    exists = os.path.exists(BLACK_SWAN_CSV)
    with open(BLACK_SWAN_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["datetime", "level", "symbol", "title", "link"])
        w.writerow([
            datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            level,
            symbol,
            title,
            link
        ])

# ===============================
# Main
# ===============================
def run():
    now = datetime.datetime.now(TZ)
    ts = now.timestamp()

    cache = load_cache()
    cache.setdefault("_l3_events", [])
    cache.setdefault("_pause_until", 0)

    # =========================
    # 🔁 L4 Auto Recover
    # =========================
    if os.path.exists(L4_ACTIVE_FILE) and ts > cache["_pause_until"]:
        os.remove(L4_ACTIVE_FILE)
        open(OBS_FLAG_FILE, "w").write(str(ts))

        if BLACK_SWAN_WEBHOOK_URL:
            requests.post(
                BLACK_SWAN_WEBHOOK_URL,
                json={
                    "content": (
                        f"📊 **L4 黑天鵝結束回顧**\n"
                        f"🕒 {now:%Y-%m-%d %H:%M}\n"
                        "▶️ 系統進入 Observation（24h）\n"
                        "▶️ AI 模型即將恢復正常"
                    )
                },
                timeout=10,
            )

    # =========================
    # Symbols from AI history
    # =========================
    symbols = set()
    for f in ["tw_history.csv", "us_history.csv"]:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            df = pd.read_csv(p)
            latest = df["date"].max()
            symbols |= set(df[df["date"] == latest]["symbol"].tolist())

    normal_embeds = []
    black_embeds = []

    # =========================
    # News Loop
    # =========================
    for sym in symbols:
        news = get_news(sym.split(".")[0])
        if not news:
            continue

        if cache.get(sym) == news["title"]:
            continue
        cache[sym] = news["title"]

        lv = get_black_swan_level(news["title"])
        final = lv

        # L3 → L4
        if lv == 3:
            cache["_l3_events"].append(ts)
            window = ts - L4_TIME_WINDOW_HOURS * 3600
            cache["_l3_events"] = [t for t in cache["_l3_events"] if t >= window]

            if len(cache["_l3_events"]) >= L4_TRIGGER_COUNT:
                final = 4
                cache["_pause_until"] = ts + L4_NEWS_PAUSE_HOURS * 3600
                open(L4_ACTIVE_FILE, "w").write(str(ts))

        # ---------------------
        # Black Swan
        # ---------------------
        if final >= 3:
            black_embeds.append({
                "title": f"{sym} | 黑天鵝 L{final}",
                "url": news["link"],
                "color": 0x8E0000 if final == 4 else 0xE74C3C,
                "fields": [{
                    "name": f"🚨 黑天鵝 L{final}",
                    "value": (
                        f"[{news['title']}]({news['link']})\n"
                        f"🕒 {news['time']}\n"
                        f"{'📍 L4 active' if final == 4 else ''}"
                    ),
                    "inline": False
                }]
            })
            log_black_swan(final, sym, news["title"], news["link"])

        # ---------------------
        # Normal News
        # ---------------------
        elif ts > cache["_pause_until"]:
            normal_embeds.append({
                "title": f"{sym} | 市場新聞",
                "url": news["link"],
                "color": 0x3498DB,
                "fields": [{
                    "name": "📰 新聞",
                    "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                    "inline": False
                }]
            })

    # =========================
    # Send Discord
    # =========================
    if normal_embeds and NEWS_WEBHOOK_URL:
        requests.post(
            NEWS_WEBHOOK_URL,
            json={
                "content": f"📰 市場新聞 | {now:%Y-%m-%d %H:%M}",
                "embeds": normal_embeds[:10],
            },
            timeout=15,
        )

    if black_embeds and BLACK_SWAN_WEBHOOK_URL:
        requests.post(
            BLACK_SWAN_WEBHOOK_URL,
            json={
                "content": "🚨 **黑天鵝警報**",
                "embeds": black_embeds[:10],
            },
            timeout=15,
        )

    save_cache(cache)

if __name__ == "__main__":
    run()
