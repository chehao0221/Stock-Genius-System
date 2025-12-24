import yfinance as yf
import pandas as pd
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def calc_pivot(df):
    r = df.iloc[-20:]
    p = (r['High'].max() + r['Low'].min() + r['Close'].iloc[-1]) / 3
    return round(2*p - r['High'].max(), 2), round(2*p - r['Low'].min(), 2)

def get_sp500():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url, headers={"User-Agent":"Mozilla"}).text)[0]
        return [s.replace('.', '-') for s in df["Symbol"]]
    except:
        return ["AAPL","NVDA","TSLA","MSFT","GOOGL","AMZN","META"]

def run():
    mag7 = ["AAPL","NVDA","TSLA","MSFT","GOOGL","AMZN","META"]
    watch = list(dict.fromkeys(mag7 + get_sp500()))

    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)
    feats = ["mom20","bias","vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {"pred": pred, "price": df["Close"].iloc[-1], "sup": sup, "res": res}
        except:
            continue

    horses = {k:v for k,v in results.items() if k not in mag7 and v["pred"] > 0}
    top5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg = f"🇺🇸 **美股 AI 實盤預測 ({datetime.now():%Y-%m-%d})**\n\n🏆 **Top 5**\n"
    for s in top5:
        r = results[s]
        msg += f"• **{s}** `{r['pred']:+.2%}` | `{r['price']:.2f}`\n"

    msg += "\n💎 **Magnificent 7**\n"
    for s in mag7:
        if s in results:
            msg += f"• {s} `{results[s]['pred']:+.2%}`\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]})
    else:
        print(msg)

if __name__ == "__main__":
    run()
