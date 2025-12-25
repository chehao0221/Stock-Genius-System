import os
import sys
import yfinance as yf
import pandas as pd
import requests
from xgboost import XGBRegressor
from datetime import datetime
import warnings

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

warnings.filterwarnings("ignore")

# ===============================
# L4 / Observation Flags
# ===============================
L4_ACTIVE_FILE = os.getenv("L4_ACTIVE_FILE", os.path.join(DATA_DIR, "l4_active.flag"))
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

def system_mode():
    now = datetime.now().timestamp()
    if os.path.exists(L4_ACTIVE_FILE):
        return "🔴 SYSTEM MODE：L4 ACTIVE"
    if os.path.exists(OBS_FLAG_FILE):
        try:
            last_end = float(open(OBS_FLAG_FILE).read())
            if now - last_end < 86400:
                return "🟠 SYSTEM MODE：OBSERVATION"
        except:
            pass
    return "🟢 SYSTEM MODE：NORMAL"

MODE = system_mode()

# L4 → 直接中止
if MODE.startswith("🔴"):
    print("🚨 L4 active — Taiwan AI skipped")
    sys.exit(0)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

def get_tw_300():
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        df = pd.read_html(url)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        codes = df["有價證券代號及名稱"].str.split("　").str[0]
        return [f"{c}.TW" for c in codes[codes.str.len() == 4].head(300)]
    except:
        return ["2330.TW", "2317.TW", "2454.TW"]

# ===============================
# Backtest
# ===============================
def get_settle_report():
    if not os.path.exists(HISTORY_FILE):
        return ""
    df = pd.read_csv(HISTORY_FILE)
    unsettled = df[df["settled"] == False]
    if unsettled.empty:
        return ""

    report = "\n🏁 **5 日回測結算**\n"
    for i, r in unsettled.iterrows():
        try:
            px = yf.download(r["symbol"], period="7d", auto_adjust=True, progress=False)["Close"].iloc[-1]
            ret = (px - r["entry_price"]) / r["entry_price"]
            df.at[i, "settled"] = True
            report += f"• {r['symbol']} `{ret:+.2%}`\n"
        except:
            pass

    df.to_csv(HISTORY_FILE, index=False)
    return report

# ===============================
# Main
# ===============================
def run():
    fixed = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"]
    watch = list(dict.fromkeys(fixed + get_tw_300()))

    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
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
            model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05)
            model.fit(train[feats], train["target"])

            results[s] = {
                "pred": float(model.predict(df[feats].iloc[-1:])[0]),
                "price": round(df["Close"].iloc[-1], 2),
                "sup": calc_pivot(df)[0],
                "res": calc_pivot(df)[1],
            }
        except:
            pass

    msg = f"{MODE}\n\n📊 **台股 AI 預測 ({datetime.now():%Y-%m-%d})**\n"

    top_5 = []
    if MODE.endswith("NORMAL"):
        horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
        top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

        msg += "\n🏆 **AI 海選 Top 5**\n"
        for s in top_5:
            r = results[s]
            msg += f"• {s} `{r['pred']:+.2%}`\n"
    else:
        msg += "\n⚠️ 觀察期中，暫停海選\n"

    msg += "\n🔍 **權值股監控**\n"
    for s in fixed:
        if s in results:
            msg += f"• {s} `{results[s]['pred']:+.2%}`\n"

    msg += get_settle_report()
    msg += "\n💡 僅供研究參考"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]})

    if MODE.endswith("NORMAL"):
        hist = [{
            "date": datetime.now().date(),
            "symbol": s,
            "entry_price": results[s]["price"],
            "pred_ret": results[s]["pred"],
            "settled": False,
        } for s in (top_5 + fixed) if s in results]

        if hist:
            pd.DataFrame(hist).to_csv(
                HISTORY_FILE,
                mode="a",
                header=not os.path.exists(HISTORY_FILE),
                index=False
            )

if __name__ == "__main__":
    run()
