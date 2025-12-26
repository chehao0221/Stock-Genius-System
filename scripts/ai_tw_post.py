import os, sys, warnings, requests
import yfinance as yf
import pandas as pd
from xgboost import XGBRegressor
from datetime import datetime, timedelta

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

warnings.filterwarnings("ignore")

# ===============================
# Flags
# ===============================
L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
L3_WARNING_FILE = os.path.join(DATA_DIR, "l3_warning.flag")

if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — TW AI skipped")
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")

WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_TW")
    or os.getenv("DISCORD_WEBHOOK_URL", "")
).strip()

# 🧠 動態 horizon
HORIZONS = [3, 5, 10]
MAIN_H = 3 if L3_WARNING else 5

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

def settle_history(df_price):
    if not os.path.exists(HISTORY_FILE):
        return

    hist = pd.read_csv(HISTORY_FILE)
    if "exit_price" not in hist.columns:
        hist["exit_price"] = None
        hist["real_ret"] = None
        hist["hit"] = None

    for i, r in hist.iterrows():
        if pd.notna(r["exit_price"]):
            continue

        entry_date = pd.to_datetime(r["date"])
        horizon = int(r.get("horizon", 5))
        symbol = r["symbol"]

        if symbol not in df_price:
            continue

        px = df_price[symbol]
        future = px[px.index >= entry_date]

        if len(future) > horizon:
            exit_price = future.iloc[horizon]["Close"]
            real_ret = exit_price / r["entry_price"] - 1
            hist.loc[i, "exit_price"] = round(exit_price, 2)
            hist.loc[i, "real_ret"] = round(real_ret, 4)
            hist.loc[i, "hit"] = (real_ret * r["pred_ret"]) > 0

    hist.to_csv(HISTORY_FILE, index=False)

# ===============================
# Main
# ===============================
def run():
    symbols = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]

    data = yf.download(
        symbols, period="2y", auto_adjust=True,
        group_by="ticker", progress=False
    )

    settle_history(data)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in symbols:
        try:
            df = data[s].dropna()
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

            preds = {}
            for h in HORIZONS:
                df["target"] = df["Close"].shift(-h) / df["Close"] - 1
                train = df.iloc[:-h].dropna()
                model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05)
                model.fit(train[feats], train["target"])
                preds[h] = float(model.predict(df[feats].iloc[-1:])[0])

            sup, res = calc_pivot(df)
            results[s] = {
                "price": df["Close"].iloc[-1],
                "preds": preds,
                "sup": sup,
                "res": res,
            }
        except:
            continue

    mode = "🟡 **SYSTEM MODE：RISK WARNING (L3)**" if L3_WARNING else "🟢 **SYSTEM MODE：NORMAL**"
    msg = f"{mode}\n\n📊 **台股 AI 預測報告 ({datetime.now():%Y-%m-%d})**\n\n"

    for s, r in results.items():
        p = r["preds"][MAIN_H]
        msg += f"{s}：`{p:+.2%}`（{MAIN_H}日） 支撐 {r['sup']} / 壓力 {r['res']}\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    if not L3_WARNING:
        rows = []
        for s, r in results.items():
            rows.append({
                "date": datetime.now().date(),
                "symbol": s,
                "entry_price": r["price"],
                "pred_ret": r["preds"][MAIN_H],
                "horizon": MAIN_H,
                "settled": False,
            })
        pd.DataFrame(rows).to_csv(
            HISTORY_FILE, mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()
