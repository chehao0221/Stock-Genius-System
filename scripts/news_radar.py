import os, sys, json, warnings, datetime, requests, feedparser, urllib.parse
import pandas as pd

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

# ===============================
# Webhook / Flags
# ===============================
NEWS_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()

L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
L3_WARNING_FILE = os.path.join(DATA_DIR, "l3_warning.flag")
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")

TZ = datetime.timezone(datetime.timedelta(hours=8))
warnings.filterwarnings("ignore")

# ===============================
# Config
# ===============================
L4_TIME_WINDOW_HOURS = 6
L4_TRIGGER_COUNT = 2
L4_NEWS_PAUSE_HOURS = 24
L3_COOLDOWN_HOURS = 6

DISCLAIMER = "📌 提醒：僅為風險與市場監控，非投資建議"

# ===============================
# Black Swan Levels
# ===============================
BLACK_SWAN_LEVELS = {
    3: ["破產", "下市", "bankruptcy", "delist", "halt"],
    2: ["制裁", "違約", "lawsuit", "sec", "sanction"],
    1: ["裁員", "停產", "調查"],
}

def get_black_swan_level(title: str) -> int:
    t = title.lower()
    for level, keys in BLACK_SWAN_LEVELS.items():
        if any(k.lower() in t for k in keys):
            return level
    return 0

# ===============================
# Cache
# ===============================
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

# ===============================
# News Fetch
# ===============================
def get_news(q):
    try:
        url = (
            "https://news.google.com/rss/search?"
            f"q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
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
    except:
        return None

# ===============================
# Main
# ===============================
def run():
    now = datetime.datetime.now(TZ)
    ts = now.timestamp()

    cache = load_cache()
    cache.setdefault("_l3_events", [])
    cache.setdefault("_l4_pause_until", 0)

    # ===============================
    # 🔁 L4 Auto Recover
    # ===============================
    if os.path.exists(L4_ACTIVE_FILE) and ts > cache["_l4_pause_until"]:
        os.remove(L4_ACTIVE_FILE)
        open(OBS_FLAG_FILE, "w").write(str(ts))

        if BLACK_SWAN_WEBHOOK_URL:
            requests.post(
                BLACK_SWAN_WEBHOOK_URL,
                json={
                    "content": (
                        "📊 **L4 黑天鵝事件結束**\n"
                        f"🕒 {now:%Y-%m-%d %H:%M}\n"
                        "🟠 系統已進入風險觀察期\n\n"
                        f"{DISCLAIMER}"
                    )
                },
                timeout=15,
            )

    # ===============================
    # 今日 AI 監控標的
    # ===============================
    symbols = []
    for f in ["tw_history.csv", "us_history.csv"]:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            df = pd.read_csv(p)
            latest = df["date"].max()
            symbols += df[df["date"] == latest]["symbol"].tolist()

    black_embeds = []

    for s in set(symbols):
        news = get_news(s.split(".")[0])
        if not news:
            continue

        level = get_black_swan_level(news["title"])
        final_level = level

        # ===== L3 記錄 =====
        if level == 3:
            cache["_l3_events"].append(ts)
            cache["_l3_events"] = [
                t for t in cache["_l3_events"]
                if ts - t <= L4_TIME_WINDOW_HOURS * 3600
            ]

            # ===== 升級 L4 =====
            if len(cache["_l3_events"]) >= L4_TRIGGER_COUNT:
                final_level = 4
                cache["_l4_pause_until"] = ts + L4_NEWS_PAUSE_HOURS * 3600
                open(L4_ACTIVE_FILE, "w").write(str(ts))
                if os.path.exists(L3_WARNING_FILE):
                    os.remove(L3_WARNING_FILE)

        # ===== L3 Warning（只發一次）=====
        if level == 3 and not os.path.exists(L4_ACTIVE_FILE):
            if not os.path.exists(L3_WARNING_FILE):
                open(L3_WARNING_FILE, "w").write(str(ts))
                if BLACK_SWAN_WEBHOOK_URL:
                    requests.post(
                        BLACK_SWAN_WEBHOOK_URL,
                        json={
                            "content": (
                                "🟡 **SYSTEM MODE：風險警示（L3）**\n"
                                f"🕒 {now:%Y-%m-%d %H:%M}\n"
                                "⚠️ 偵測到高風險事件，系統將降低進攻行為\n\n"
                                f"{DISCLAIMER}"
                            )
                        },
                        timeout=15,
                    )

        # ===== Embed =====
        if final_level >= 3:
            black_embeds.append({
                "title": f"{s} | 黑天鵝 L{final_level}",
                "url": news["link"],
                "color": 0x8E0000,
                "fields": [{
                    "name": f"🚨 黑天鵝 L{final_level}",
                    "value": f"[{news['title']}]({news['link']})\n🕒 {news['time']}",
                    "inline": False
                }]
            })

    # ===== L3 冷卻解除 =====
    if os.path.exists(L3_WARNING_FILE):
        recent = [t for t in cache["_l3_events"]
                  if ts - t <= L3_COOLDOWN_HOURS * 3600]
        if not recent:
            os.remove(L3_WARNING_FILE)

    # ===== Send =====
    if black_embeds and BLACK_SWAN_WEBHOOK_URL:
        requests.post(
            BLACK_SWAN_WEBHOOK_URL,
            json={
                "content": f"🚨 **黑天鵝警報**\n\n{DISCLAIMER}",
                "embeds": black_embeds[:10]
            },
            timeout=15,
        )

    save_cache(cache)

if __name__ == "__main__":
    run()
