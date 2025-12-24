import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# =========================
# 基本設定
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# 工具
# =========================
def calc_pivot(df):
    recent = df.iloc[-20:]
    h, l, c = recent['High'].max(), recent['Low'].min(), recent['Close'].iloc[-1]
    p = (h + l + c) / 3
    return round(2*p - h, 1), round(2*p - l, 1)

def get_tw_pool():
    try:
        import requests
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        df = pd.read_html(requests.get(url, timeout=10).text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        codes = df["有價證券代號及名稱"].str.split("　").str[0]
        codes = codes[codes.str.len() == 4].head(300)
        return [f"{c}.TW" for c in codes]
    except:
        return ["2330.TW", "2317.TW", "2454.TW"]

# =========================
# 回測結算（實盤安全）
# =========================
def settle_report():
    if not os.path.exists(HISTORY_FILE):
        return ""

    df = pd.read_csv(HISTORY_FILE)
    unsettled = df[df["settled"] == False]
    if unsettled.empty:
        return "\n📊 **5 日回測**：尚無可結算資料"

    report = "\n🏁 **台股 5 日回測結算**\n"
    for idx, row in unsettled.iterrows():
        try:
            df_price = yf.download(row["symbol"], period="7d", auto_adjust=True, progress=False)
            exit_p = df_price["Close"].iloc[-1]
            ret = (exit_p - row["entry_price"]) / row["entry_price"]
            win = (ret > 0 and row["pred_ret"] > 0) or (ret < 0 and row["pred_ret"] < 0)
            report += f"• `{row['symbol']}` 預估 {row['pred_ret']:+.2%} | 實際 `{ret:+.2%}` {'✅' if win else '❌'}\n"
            df.at[idx, "settled"] = True
        except:
            continue

    df.to_csv(HISTORY_FILE, index=False)
    return report

# =========================
# 主程式
# =========================
def run():
    fixed = ["2330.TW", "2317.TW", "2454.TW"]
    watch = list(dict.fromkeys(fixed + get_tw_pool()))

    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 120:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.05,
                random_state=42
            )
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": float(df["Close"].iloc[-1]),
                "sup": sup,
                "res": res
            }
        except:
            continue

    horses = {k:v for k,v in results.items() if k not in fixed and v["pred"] > 0}
    top5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg = f"📊 **台股 AI 實盤預測 ({datetime.now():%Y-%m-%d})**\n\n🏆 **Top 5 黑馬**\n"
    for s in top5:
        r = results[s]
        msg += f"• **{s}** `{r['pred']:+.2%}` | 價 `{r['price']}` (Pivot `{r['sup']}/{r['res']}`)\n"

    msg += "\n🔍 **權值股**\n"
    for s in fixed:
        if s in results:
            r = results[s]
            msg += f"• {s} `{r['pred']:+.2%}`\n"

    msg += settle_report()
    msg += "\n💡 僅供研究參考，實盤請自行控管風險"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]})
    else:
        print(msg)

    hist = [{
        "date": datetime.now().date(),
        "symbol": s,
        "entry_price": results[s]["price"],
        "pred_ret": results[s]["pred"],
        "settled": False
    } for s in top5 + fixed if s in results]

    pd.DataFrame(hist).to_csv(
        HISTORY_FILE,
        mode="a",
        header=not os.path.exists(HISTORY_FILE),
        index=False
    )

if __name__ == "__main__":
    run()
