import os, sys, json, csv, warnings, datetime, requests, feedparser, urllib.parse
import pandas as pd
import yfinance as yf

# ===============================
# Base / Paths
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

# ===============================
# Environment
# ===============================
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

BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "sec", "sanction"],
    1: ["裁員", "停產", "調查"],
}

# ===============================
# Utils
# ===============================
def get_black_swan_level(title: str) -> int:
    t = title.lower()
    for lv, keys in BLACK_SWAN_LEVELS.items():
        if any(k.lower() in t for k in keys):
            return lv
    return 0

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def get_news(query):
    url = (
        "https://news.google.com/rss/search?"
        f"q={urllib.parse.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
    )
    feed = feedparser.parse(url)
    if not feed.entries:
        return None
    e = feed.entries[0]
    return {
        "title": e.title.split(" - ")[0],
        "link": e.link,
        "time": datetime.datetime(
            *e.published_parsed[:6],
            tzinfo=datetime.timezone.utc
        ).astimezone(TZ).strftime("%H:%M")
    }

def log_black_swan(level, symbol, title, link):
    exists = os.path.exists(BLACK_SWAN_CSV)
    with open(BLACK_SWAN_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["datetime", "level", "symbol", "title", "link"])
        w.writerow([
            datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            level, symbol, title, link
        ])

def get_today_symbols():
    syms = []
    for f in ["tw_history.csv", "us_history.csv"]:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            df = pd.read_csv(p)
            latest = df["date"].max()
            syms += df[df["date"] == latest]["symbol"].tolist()
    return list(set(syms))

# ===============================
# Main
# ===============================
def run():
    now = datetime.datetime.now(TZ)
    ts = now.timestamp()

    cache = load_cache()
    cache.setdefault("_l3_events", [])
    cache.setdefault("_l4_pause_until", 0)

    # ===========================
    # 🔔 L4 Auto Recovery
    # ===========================
    if os.path.exists(L4_ACTIVE_FILE) and ts > cache["_l4_pause_until"]:
        os.remove(L4_ACTIVE_FILE)
        open(OBS_FLAG_FILE, "w").write(str(ts))

        if BLACK_SWAN_WEBHOOK_URL:
            requests.post(
                BLACK_SWAN_WEBHOOK_URL,
                json={
                    "content": (
                        "📊 **L4 黑天鵝事件結束回顧**\n"
                        f"🕒 {now:%Y-%m-%d %H:%M}\n"
                        "🟠 SYSTEM MODE：OBSERVATION\n"
                        "▶️ AI 已恢復，但暫停激進推薦"
                    )
                },
                timeout=15,
            )

    # ===========================
    # SYSTEM MODE
    # ===========================
    if os.path.exists(L4_ACTIVE_FILE):
        system_mode = "🔴 SYSTEM MODE：L4 ACTIVE"
    elif os.path.exists(OBS_FLAG_FILE) and ts - float(open(OBS_FLAG_FILE).read()) < 86400:
        system_mode = "🟠 SYSTEM MODE：OBSERVATION"
    else:
        system_mode = "🟢 SYSTEM MODE：NORMAL"

    symbols = get_today_symbols()
    normal, black = [], []

    for s in symbols:
        n = get_news(s.split(".")[0])
        if not n:
            continue

        lv = get_black_swan_level(n["title"])
        final = lv

        if lv == 3:
            cache["_l3_events"].append(ts)
            cache["_l3_events"] = [
                t for t in cache["_l3_events"]
                if ts - t <= L4_TIME_WINDOW_HOURS * 3600
            ]
            if len(cache["_l3_events"]) >= L4_TRIGGER_COUNT:
                final = 4
                cache["_l4_pause_until"] = ts + L4_NEWS_PAUSE_HOURS * 3600
                open(L4_ACTIVE_FILE, "w").write(str(ts))

        if final >= 3:
            black.append({
                "title": f"{s} | 黑天鵝 L{final}",
                "url": n["link"],
                "color": 0x8E0000,
                "fields": [{
                    "name": f"🚨 黑天鵝 L{final}",
                    "value": f"[{n['title']}]({n['link']})\n🕒 {n['time']}",
                    "inline": False
                }]
            })
            log_black_swan(final, s, n["title"], n["link"])

        elif ts > cache["_l4_pause_until"]:
            normal.append({
                "title": f"{s} | 市場新聞",
                "url": n["link"],
                "color": 0x3498DB,
                "fields": [{
                    "name": "📰 市場新聞",
                    "value": f"[{n['title']}]({n['link']})\n🕒 {n['time']}",
                    "inline": False
                }]
            })

    if normal and NEWS_WEBHOOK_URL:
        requests.post(
            NEWS_WEBHOOK_URL,
            json={
                "content": f"{system_mode}\n📅 {now:%Y-%m-%d %H:%M}",
                "embeds": normal[:10],
            },
            timeout=15,
        )

    if black and BLACK_SWAN_WEBHOOK_URL:
        requests.post(
            BLACK_SWAN_WEBHOOK_URL,
            json={
                "content": f"{system_mode}\n🚨 黑天鵝警報",
                "embeds": black[:10],
            },
            timeout=15,
        )

    save_cache(cache)

if __name__ == "__main__":
    run()
