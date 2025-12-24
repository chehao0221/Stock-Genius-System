import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse
import pandas as pd
import json
import warnings

warnings.filterwarnings("ignore")
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/news_cache.json"

def get_live_news(query):
    """抓取 Google News 並過濾 12 小時內的最新消息"""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        if feed.entries:
            entry = feed.entries[0]
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            now_time = datetime.datetime.utcnow()
            if (now_time - pub_time).total_seconds() / 3600 > 12:
                return None
            return {
                "title": entry.title.split(" - ")[0], 
                "link": entry.link,
                "time": (pub_time + datetime.timedelta(hours=8)).strftime("%H:%M")
            }
        return None
    except: return None

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

def get_ai_top_symbols(market="TW"):
    """自動從 AI 預測紀錄中抓取最新的 Top 5 標的"""
    try:
        file_path = "data/tw_history.csv" if market == "TW" else "data/us_history.csv"
        if not os.path.exists(file_path): return []
        df = pd.read_csv(file_path)
        # 取得最近一次預測日期
        latest_date = df['date'].max()
        top_5 = df[df['date'] == latest_date].sort_values(by='pred_ret', ascending=False).head(5)
        return top_5['symbol'].tolist()
    except:
        return []

def run():
    if not DISCORD_WEBHOOK_URL: return
    
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    news_cache = load_cache()
    new_messages = []

    # --- 💡 自動判定市場並抓取 AI 標的 ---
    if now.hour < 12:
        market_title = "🏹 AI 台股海選雷達"
        # 優先抓取 AI 海選標的，若無則用預設權值
        ai_symbols = get_ai_top_symbols("TW")
        watch_list = {s: "AI 海選強勢股" for s in ai_symbols} if ai_symbols else {"2330.TW": "台積電", "2317.TW": "鴻海"}
    else:
        market_title = "⚡ AI 美股海選雷達"
        ai_symbols = get_ai_top_symbols("US")
        watch_list = {s: "AI 海選強勢股" for s in ai_symbols} if ai_symbols else {"NVDA": "輝達", "TSLA": "特斯拉"}

    for sym, label in watch_list.items():
        try:
            # 針對搜尋詞優化：2330.TW -> 2330
            search_key = sym.split('.')[0]
            news = get_live_news(search_key)
            if not news or news_cache.get(sym) == news['title']:
                continue
            
            news_cache[sym] = news['title']
            
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2d")
            curr_p = df['Close'].iloc[-1]
            change_pct = ((curr_p - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
            
            color = 0xFF4500 if change_pct > 0 else 0x1E90FF
            
            embed = {
                "title": f"{sym} | {label}",
                "description": f"AI 預測目標標的 - **最新消息**",
                "color": color,
                "fields": [
                    {"name": "💵 當前報價", "value": f"`{curr_p:.2f}` ({change_pct:+.2f}%)", "inline": True},
                    {"name": "🗞️ 焦點頭條", "value": f"[{news['title']}]({news['link']}) \n*(🕒 {news['time']})*", "inline": False}
                ],
                "footer": {"text": "Quant Master AI-Radar"}
            }
            new_messages.append(embed)
        except: continue

    if new_messages:
        requests.post(DISCORD_WEBHOOK_URL, json={
            "content": f"### {market_title}\n📅 `{now.strftime('%H:%M')}` AI 自動追蹤新消息\n" + "━"*15
        })
        for msg in new_messages:
            requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [msg]})
        save_cache(news_cache)

if __name__ == "__main__":
    run()
