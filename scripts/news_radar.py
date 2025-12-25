import os, sys, json, csv, warnings, datetime, requests, feedparser, urllib.parse
import pandas as pd

# ===============================
# Base / Paths
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

# ===============================
# Env
# ===============================
NEWS_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
BLACK_SWAN_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()

L4_ACTIVE_FILE = os.getenv("L4_ACTIVE_FILE", os.path.join(DATA_DIR, "l4_active.flag"))
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

CACHE_FILE = os.path.join(DATA_DIR, "news_cache.json")
BLACK_SWAN_CSV = os.path.join(DATA_DIR, "black_swan_history.csv")
STATE_LOG_CSV = os.path.join(DATA_DIR, "system_state_log.csv")

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
# Utils
# ===============================
def log_state(state, note=""):
    exists = os.path.exists(STATE_LOG_CSV)
    with open(STATE_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["datetime", "state", "note"])
        w.writerow([
            datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            state, note
        ])

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def get_black_swan_level(title):
    t = title.lower()
    for lv, keys in BLACK_SWAN_LEVELS.items():
        if any(k.lower() in t for k in keys):
            return lv
    return 0

def get_news(q):
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
    cache.setdefault("_l4_start", None)
    cache.setdefault("_l4_pause_until", 0)
    cache.setdefault("_l4_symbols", [])

    # 🔁 L4 → OBSERVATION
    if os.path.exists(L4_ACTIVE_FILE) and ts > cache["_l4_pause_until"]:
        os.remove(L4_ACTIVE_FILE)
        open(OBS_FLAG_FILE, "w").write(str(ts))
        log_state("L4_END", "auto recover to observation")

        # 📊 L4 Timeline Report
        if BLACK_SWAN_WEBHOOK_URL:
            duration = int((ts - cache["_l4_start"]) / 60) if cache["_l4_start"] else "?"
            symbols = ", ".join(set(cache["_l4_symbols"]))

            requests.post(
                BLACK_SWAN_WEBHOOK_URL,
                json={
                    "content": (
                        "📊 **L4 黑天鵝事件時間線回顧**\n"
                        f"🕒 開始：{datetime.datetime.fromtimestamp(cache['_l4_start'], TZ):%Y-%m-%d %H:%M}\n"
                        f"🕒 結束：{now:%Y-%m-%d %H:%M}\n"
                        f"⏱ 持續：約 {duration} 分鐘\n"
                        f"🎯 相關標的：{symbols}\n\n"
                        "🟠 SYSTEM MODE：OBSERVATION"
                    )
                },
                timeout=15,
            )

        cache["_l4_start"] = None
        cache["_l4_symbols"] = []

    # 🔔 OBSERVATION → NORMAL
    if os.path.exists(OBS_FLAG_FILE):
        last_end = float(open(OBS_FLAG_FILE).read())
        if ts - last_end > OBSERVATION_HOURS * 3600:
            os.remove(OBS_FLAG_FILE)
            log_state("OBS_END", "back to normal")

            if NEWS_WEBHOOK_URL:
                requests.post(
                    NEWS_WEBHOOK_URL,
                    json={"content": "🟢 **SYSTEM MODE：NORMAL**\nAI 分析與海選已全面恢復"},
                    timeout=15,
                )

    symbols = get_today_symbols()
    for s in symbols:
        n = get_news(s.split(".")[0])
        if not n:
            continue

        lv = get_black_swan_level(n["title"])
        if lv == 3:
            cache["_l3_events"].append(ts)
            cache["_l3_events"] = [
                t for t in cache["_l3_events"]
                if ts - t <= L4_TIME_WINDOW_HOURS * 3600
            ]

            if len(cache["_l3_events"]) >= L4_TRIGGER_COUNT and not os.path.exists(L4_ACTIVE_FILE):
                open(L4_ACTIVE_FILE, "w").write(str(ts))
                cache["_l4_start"] = ts
                cache["_l4_pause_until"] = ts + L4_NEWS_PAUSE_HOURS * 3600
                log_state("L4_START", "triggered by L3 burst")

        if lv >= 3:
            cache["_l4_symbols"].append(s)

    save_cache(cache)

if __name__ == "__main__":
    run()
