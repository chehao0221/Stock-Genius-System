import os, sys, json, csv, warnings, datetime, requests, feedparser, urllib.parse, subprocess
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
BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")

TZ = datetime.timezone(datetime.timedelta(hours=8))
warnings.filterwarnings("ignore")

# ===============================
# 🔧 Tunable Risk Policy（新增）
# ===============================
L4_TIME_WINDOW_HOURS = 6
L4_TRIGGER_COUNT = 2
L4_BASE_PAUSE_HOURS = 24

L4_COOLDOWN_HOURS = 12          # 🔒 L4 結束後冷卻期（防抖動）
L4_EXIT_L3_THRESHOLD = 1        # 🔍 L4 結束前，最近 L3 次數門檻
L4_EXIT_LOOKBACK_HOURS = 6

DISCLAIMER = "📌 僅為風險與市場監控，非投資建議"

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
# Cache Helpers
# ===============================
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {
        "_l3_events": [],
        "_l4_pause_until": 0,
        "_l4_recovered_at": 0
    }

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

    # ===============================
    # 🔁 L4 Auto Recover（強化版）
    # ===============================
    if os.path.exists(L4_ACTIVE_FILE) and ts > cache["_l4_pause_until"]:
        recent_l3 = [
            t for t in cache["_l3_events"]
            if ts - t <= L4_EXIT_LOOKBACK_HOURS * 3600
        ]

        if len(recent_l3) <= L4_EXIT_L3_THRESHOLD:
            os.remove(L4_ACTIVE_FILE)
            open(OBS_FLAG_FILE, "w").write(str(ts))
            cache["_l4_recovered_at"] = ts

            if BLACK_SWAN_WEBHOOK_URL:
                requests.post(
                    BLACK_SWAN_WEBHOOK_URL,
                    json={
                        "content": (
                            "📊 **L4 黑天鵝事件結束（風險降溫）**\n"
                            f"🕒 {now:%Y-%m-%d %H:%M}\n\n"
                            f"{DISCLAIMER}"
                        )
                    },
                    timeout=15,
                )

            subprocess.run(["python", "scripts/l4_ai_performance_report.py"])
            subprocess.run(["python", "scripts/l4_ai_performance_compare.py"])
        else:
            # 🔥 延長 L4
            cache["_l4_pause_until"] += 12 * 3600

    # ===============================
    # 今日 AI 標的
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

        # ===============================
        # L3 記錄
        # ===============================
        if level == 3:
            cache["_l3_events"].append(ts)
            cache["_l3_events"] = [
                t for t in cache["_l3_events"]
                if ts - t <= L4_TIME_WINDOW_HOURS * 3600
            ]

            # ===============================
            # L4 升級（含冷卻期）
            # ===============================
            in_cooldown = (
                ts - cache.get("_l4_recovered_at", 0)
                < L4_COOLDOWN_HOURS * 3600
            )

            if (
                not os.path.exists(L4_ACTIVE_FILE)
                and not in_cooldown
                and len(cache["_l3_events"]) >= L4_TRIGGER_COUNT
            ):
                final_level = 4
                cache["_l4_pause_until"] = ts + L4_BASE_PAUSE_HOURS * 3600
                open(L4_ACTIVE_FILE, "w").write(str(ts))

        # ===============================
        # Discord Embed
        # ===============================
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
