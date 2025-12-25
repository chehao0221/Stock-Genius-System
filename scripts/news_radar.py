import os
import sys
import yfinance as yf
import requests
import datetime
import feedparser
import urllib.parse
import warnings

# 忽略 yfinance 警告
warnings.filterwarnings("ignore")

# =============================
# 1. 基礎與環境設定
# =============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = os.path.join(DATA_DIR, "news_cache.txt")
TZ_TW = datetime.timezone(datetime.timedelta(hours=8))

MAX_EMBEDS = 8
NEWS_HOURS_LIMIT = 12
PRICE_CACHE = {}

# =============================
# 2. 股價與指數獲取系統
# =============================
def get_stock_price(sym):
    if sym in PRICE_CACHE: return PRICE_CACHE[sym]
    try:
        t = yf.Ticker(sym)
        info = t.fast_info
        price = info.get("last_price") or t.info.get("regularMarketPrice")
        prev = info.get("previous_close") or t.info.get("regularMarketPreviousClose")
        if price and prev:
            pct = ((price - prev) / prev) * 100
            PRICE_CACHE[sym] = (price, pct)
            return price, pct
    except: pass
    PRICE_CACHE[sym] = (None, None)
    return None, None

def get_market_price(market_type):
    try:
        sym = "^TWII" if market_type == "TW" else "^IXIC"
        name = "加權指數" if market_type == "TW" else "那斯達克"
        t = yf.Ticker(sym)
        info = t.fast_info
        cur = info.get("last_price") or t.info.get("regularMarketPrice")
        prev = info.get("previous_close") or t.info.get("regularMarketPreviousClose")
        if not cur or not prev: return "⚠️ 資料讀取中"
        pct = ((cur - prev) / prev) * 100
        emoji = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
        return f"{emoji} {name}: {cur:.2f} ({pct:+.2f}%)"
    except: return "⚠️ 指數取得失敗"

# =============================
# 3. 個股對照表 (AI 核心標的)
# =============================
STOCK_MAP = {
    "台積電": {"sym": "2330.TW", "desc": "AI晶片 / 先進製程"},
    "2330": {"sym": "2330.TW", "desc": "AI晶片 / 先進製程"},
    "鴻海": {"sym": "2317.TW", "desc": "AI伺服器 / 組裝"},
    "聯發科": {"sym": "2454.TW", "desc": "IC設計"},
    "廣達": {"sym": "2382.TW", "desc": "AI伺服器代工"},
    "奇鋐": {"sym": "3017.TW", "desc": "AI散熱龍頭"},
    "00929": {"sym": "00929.TW", "desc": "科技優息"},
    "00919": {"sym": "00919.TW", "desc": "精選高息"},
    "輝達": {"sym": "NVDA", "desc": "NVIDIA / AI龍頭"},
    "NVIDIA": {"sym": "NVDA", "desc": "NVIDIA / AI龍頭"},
    "特斯拉": {"sym": "TSLA", "desc": "Tesla"},
    "TSLA": {"sym": "TSLA", "desc": "Tesla"},
    "蘋果": {"sym": "AAPL", "desc": "Apple"},
    "AAPL": {"sym": "AAPL", "desc": "Apple"},
    "微軟": {"sym": "MSFT", "desc": "Microsoft"},
    "PLTR": {"sym": "PLTR", "desc": "AI數據分析"},
}

STOCK_WEIGHT = {"2330.TW": 5, "NVDA": 5, "AAPL": 4, "2454.TW": 4, "PLTR": 3}

def pick_most_important_stock(title):
    hits = []
    title_lower = title.lower()
    seen_sym = set()
    for key, info in STOCK_MAP.items():
        if key.lower() in title_lower:
            sym = info["sym"]
            if sym in seen_sym: continue
            seen_sym.add(sym)
            weight = STOCK_WEIGHT.get(sym, 1)
            # 分數 = 權重 * 100 - 出現位置 (越前面越重要)
            hits.append((weight * 100 - title_lower.find(key.lower()), info))
    if not hits: return None
    return sorted(hits, reverse=True)[0][1]

# =============================
# 4. Discord 訊息生成
# =============================
def create_news_embed(post, market_type):
    color = 0x3498db if market_type == "TW" else 0xe74c3c
    target = pick_most_important_stock(post["title"])

    if target:
        price, pct = get_stock_price(target["sym"])
        if price is not None:
            trend = "📈 利多" if pct > 0 else "📉 利空" if pct < 0 else "➖ 中性"
            return {
                "title": f"📊 {target['sym']} | {target['desc']}",
                "url": post["link"],
                "color": color,
                "fields": [
                    {"name": "⚖️ 市場判斷", "value": trend, "inline": True},
                    {"name": "💵 即時價格", "value": f"**{price:.2f} ({pct:+.2f}%)**", "inline": True},
                    {"name": "📰 焦點新聞", "value": f"[{post['title']}]({post['link']})\n🕒 {post['time']}", "inline": False},
                ],
                "footer": {"text": "Quant Master Radar"}
            }
    
    return {
        "title": post["title"],
        "url": post["link"],
        "color": color,
        "fields": [
            {"name": "🕒 發布時間", "value": f"{post['time']} (台北)", "inline": True},
            {"name": "📰 新聞來源", "value": post["source"], "inline": True},
        ],
        "footer": {"text": "Quant Master Radar"}
    }

# =============================
# 5. 主流程邏輯
# =============================
def run_radar():
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：未設定 NEWS_WEBHOOK_URL"); return

    # 讀取快取
    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = {l.strip() for l in f if l.strip()}

    now_tw = datetime.datetime.now(TZ_TW)
    market_type = "TW" if 7 <= now_tw.hour < 16 else "US"
    
    queries = (["台股 財經", "台積電 鴻海 聯發科"] if market_type == "TW" 
               else ["美股 盤前", "輝達 NVIDIA 特斯拉", "PLTR 財報"])

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    collected = {}

    for q in queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        for e in feed.entries[:10]:
            title = e.title.split(" - ")[0]
            if title in sent_titles or title in collected: continue
            if not hasattr(e, "published_parsed"): continue
            pub_utc = datetime.datetime(*e.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (now_utc - pub_utc).total_seconds() / 3600 > NEWS_HOURS_LIMIT: continue
            
            collected[title] = {
                "title": title, "link": e.link, "source": e.title.split(" - ")[-1],
                "time": pub_utc.astimezone(TZ_TW).strftime("%H:%M"), "sort": pub_utc,
            }

    posts = sorted(collected.values(), key=lambda x: x["sort"], reverse=True)[:MAX_EMBEDS]
    if not posts: return

    embeds = [create_news_embed(p, market_type) for p in posts]
    
    # 發送至 Discord
    market_label = "🏹 台股即時雷達" if market_type == "TW" else "⚡ 美股即時雷達"
    payload = {
        "content": f"## {market_label}\n📊 **{get_market_price(market_type)}**\n📅 台北時間: `{now_tw.strftime('%Y-%m-%d %H:%M')}`\n{'-'*25}",
        "embeds": embeds
    }
    
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code in (200, 204):
            # 成功後更新快取 (保留最新 300 條)
            new_cache = (list(sent_titles) + [p["title"] for p in posts])[-300:]
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                for t in new_cache: f.write(f"{t}\n")
            print(f"✅ 推播成功: {len(posts)} 則")
    except Exception as e:
        print(f"❌ 推播失敗: {e}")

if __name__ == "__main__":
    run_radar()
