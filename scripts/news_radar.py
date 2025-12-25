import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse
import sys

# =============================
# 專案路徑與基礎設定
# =============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, \"data\")
os.makedirs(DATA_DIR, exist_ok=True)

DISCORD_WEBHOOK_URL = os.getenv(\"NEWS_WEBHOOK_URL\", \"\").strip()
CACHE_FILE = os.path.join(DATA_DIR, \"news_cache.txt\")
TZ_TW = datetime.timezone(datetime.timedelta(hours=8))
MAX_EMBEDS = 8
NEWS_HOURS_LIMIT = 6  # 縮短時間限制，確保消息夠即時

PRICE_CACHE = {}

# =============================
# 股價快取系統 ( yfinance 優化版 )
# =============================
def get_stock_price(sym):
    if sym in PRICE_CACHE: return PRICE_CACHE[sym]
    try:
        t = yf.Ticker(sym)
        info = t.fast_info
        price = info.get(\"last_price\") or t.info.get(\"regularMarketPrice\")
        prev = info.get(\"previous_close\") or t.info.get(\"regularMarketPreviousClose\")
        if price and prev:
            pct = ((price - prev) / prev) * 100
            PRICE_CACHE[sym] = (price, pct)
            return price, pct
    except: pass
    PRICE_CACHE[sym] = (None, None)
    return None, None

# =============================
# 重點標的對照表 (融入 AI 系統核心標的)
# =============================
STOCK_MAP = {
    \"台積電\": {\"sym\": \"2330.TW\", \"desc\": \"AI晶片 / 先進製程\"},
    \"2330\": {\"sym\": \"2330.TW\", \"desc\": \"AI晶片 / 先進製程\"},
    \"鴻海\": {\"sym\": \"2317.TW\", \"desc\": \"AI伺服器 / 組裝\"},
    \"2317\": {\"sym\": \"2317.TW\", \"desc\": \"AI伺服器 / 組裝\"},
    \"輝達\": {\"sym\": \"NVDA\", \"desc\": \"NVIDIA / AI龍頭\"},
    \"NVIDIA\": {\"sym\": \"NVDA\", \"desc\": \"NVIDIA / AI龍頭\"},
    \"特斯拉\": {\"sym\": \"TSLA\", \"desc\": \"Tesla / 電動車\"},
    \"TSLA\": {\"sym\": \"TSLA\", \"desc\": \"Tesla / 電動車\"},
    \"蘋果\": {\"sym\": \"AAPL\", \"desc\": \"Apple / 手機端AI\"},
    \"AAPL\": {\"sym\": \"AAPL\", \"desc\": \"Apple / 手機端AI\"},
}

STOCK_WEIGHT = {\"2330.TW\": 5, \"NVDA\": 5, \"2317.TW\": 4, \"TSLA\": 4}

# =============================
# 核心邏輯：重要度判定
# =============================
def pick_most_important_stock(title):
    hits = []
    title_lower = title.lower()
    seen_sym = set()
    for key, info in STOCK_MAP.items():
        pos = title_lower.find(key.lower())
        if pos >= 0:
            sym = info[\"sym\"]
            if sym in seen_sym: continue
            seen_sym.add(sym)
            weight = STOCK_WEIGHT.get(sym, 1)
            score = weight * 100 - pos
            hits.append((score, info))
    if not hits: return None
    hits.sort(reverse=True, key=lambda x: x[0])
    return hits[0][1]

def create_news_embed(post, market_type):
    color = 0x3498db if market_type == \"TW\" else 0xe74c3c
    target = pick_most_important_stock(post[\"title\"])

    if target:
        price, pct = get_stock_price(target[\"sym\"])
        if price:
            trend = \"📈 利多\" if pct > 0 else \"📉 利空\" if pct < 0 else \"➖ 中性\"
            return {
                \"title\": f\"📊 {target['sym']} | {target['desc']}\",
                \"url\": post[\"link\"],
                \"color\": color,
                \"fields\": [
                    {\"name\": \"⚖️ 市場判斷\", \"value\": trend, \"inline\": True},
                    {\"name\": \"💵 即時價格\", \"value\": f\"**{price:.2f} ({pct:+.2f}%)**\", \"inline\": True},
                    {\"name\": \"📰 焦點新聞\", \"value\": f\"[{post['title']}]({post['link']})\\n🕒 {post['time']}\", \"inline\": False},
                ],
                \"footer\": {\"text\": \"Quant Master AI-Radar\"}
            }
    
    return {
        \"title\": post[\"title\"],
        \"url\": post[\"link\"],
        \"color\": color,
        \"fields\": [
            {\"name\": \"🕒 發布時間\", \"value\": f\"{post['time']} (台北)\", \"inline\": True},
            {\"name\": \"📰 新聞來源\", \"value\": post[\"source\"], \"inline\": True},
        ],
        \"footer\": {\"text\": \"Quant Master AI-Radar\"}
    }

# =============================
# 主執行邏輯
# =============================
def run_radar():
    if not DISCORD_WEBHOOK_URL: return
    
    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, \"r\", encoding=\"utf-8\") as f:
            sent_titles = {l.strip() for l in f if l.strip()}

    now_tw = datetime.datetime.now(TZ_TW)
    market = \"TW\" if 8 <= now_tw.hour < 17 else \"US\"
    queries = [\"台股 財經\", \"台積電 鴻海\"] if market == \"TW\" else [\"美股 盤前\", \"輝達 特斯拉\"]
    
    collected = {}
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for q in queries:
        url = f\"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW\"
        feed = feedparser.parse(url)
        for e in feed.entries[:10]:
            title = e.title.split(\" - \")[0]
            if title in sent_titles or title in collected: continue
            if not hasattr(e, \"published_parsed\"): continue
            pub_utc = datetime.datetime(*e.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (now_utc - pub_utc).total_seconds() / 3600 > NEWS_HOURS_LIMIT: continue
            
            collected[title] = {
                \"title\": title, \"link\": e.link, \"source\": e.title.split(\" - \")[-1],
                \"time\": pub_utc.astimezone(TZ_TW).strftime(\"%H:%M\"), \"sort\": pub_utc
            }

    posts = sorted(collected.values(), key=lambda x: x[\"sort\"], reverse=True)[:MAX_EMBEDS]
    if not posts: return

    embeds = [create_news_embed(p, market) for p in posts]
    
    # 分批推播 (Discord 限制一則訊息最多 10 個 embeds)
    requests.post(DISCORD_WEBHOOK_URL, json={
        \"content\": f\"### 📡 AI 金融雷達 ({'台股' if market=='TW' else '美股'}時段)\\n📅 `{now_tw.strftime('%Y-%m-%d %H:%M')}`\"
    })
    
    for i in range(0, len(embeds), 4):
        requests.post(DISCORD_WEBHOOK_URL, json={\"embeds\": embeds[i:i+4]})

    # 更新紀錄
    sent_titles.update(p[\"title\"] for p in posts)
    with open(CACHE_FILE, \"w\", encoding=\"utf-8\") as f:
        for t in list(sent_titles)[-200:]: f.write(f\"{t}\\n\")

if __name__ == \"__main__\":
    run_radar()
