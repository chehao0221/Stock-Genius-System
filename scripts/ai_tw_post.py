import os, sys, warnings, requests, json
import yfinance as yf
import pandas as pd
from xgboost import XGBRegressor
from datetime import datetime

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
HORIZON_POLICY = os.path.join(DATA_DIR, "horizon_policy.json")

if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — TW AI skipped")
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Horizon Resolver
# ===============================
def resolve_horizon():
    if os.path.exists(HORIZON_POLICY):
        try:
            with open(HORIZON_POLICY, "r") as f:
                policy = json.load(f)
            h = policy.get("tw", {}).get("best")
            if h:
                return int(h)
        except Exception:
            pass
    return 3 if L3_WARNING else 5

MAIN_H = resolve_horizon()
HORIZONS = sorted(set([3, 5, 10, MAIN_H]))

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_TW")
    or os.getenv("DISCORD_WEBHOOK_URL", "")
).strip()

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

# ===============================
# Main
# ===============================
def run():
    symbols = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]

    data = yf.download(
        symbols, period="2y", auto_adjust=True,
        group_by="ticker", progress=False
    )

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
                "pred": preds[MAIN_H],
                "sup": sup,
                "res": res,
            }
        except:
            continue

    mode = "🟡 **SYSTEM MODE：RISK WARNING (L3)**" if L3_WARNING else "🟢 **SYSTEM MODE：NORMAL**"
    msg = f"{mode}\n\n📊 **台股 AI 預測報告 ({datetime.now():%Y-%m-%d})**\n\n"

    for s, r in results.items():
        msg += f"{s}：`{r['pred']:+.2%}`（{MAIN_H}日） 支撐 {r['sup']} / 壓力 {r['res']}\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    if not L3_WARNING:
        rows = [{
            "date": datetime.now().date(),
            "symbol": s,
            "entry_price": r["price"],
            "pred_ret": r["pred"],
            "horizon": MAIN_H,
            "settled": False,
        } for s, r in results.items()]

        pd.DataFrame(rows).to_csv(
            HISTORY_FILE, mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()
