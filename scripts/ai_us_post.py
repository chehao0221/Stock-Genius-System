import os, sys, warnings, requests, json
import yfinance as yf
import pandas as pd
from xgboost import XGBRegressor
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.append(BASE_DIR)

warnings.filterwarnings("ignore")

L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
L3_WARNING_FILE = os.path.join(DATA_DIR, "l3_warning.flag")

if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — US AI skipped")
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
POLICY_FILE = os.path.join(DATA_DIR, "horizon_policy.json")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_US", "").strip()

if os.path.exists(POLICY_FILE):
    policy = json.load(open(POLICY_FILE, "r", encoding="utf-8"))
    MAIN_H = int(policy.get("us", 5))
else:
    MAIN_H = 5

def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

def calc_horizon_hit_rate(history_file, horizon, lookback=30):
    if not os.path.exists(history_file):
        return None, 0
    df = pd.read_csv(history_file)
    if "real_ret" not in df.columns:
        return None, 0
    df = df[df["horizon"] == horizon].dropna(subset=["pred_ret", "real_ret"]).tail(lookback)
    if len(df) < 10:
        return None, len(df)
    hit = ((df["pred_ret"] > 0) & (df["real_ret"] > 0)) | \
          ((df["pred_ret"] < 0) & (df["real_ret"] < 0))
    return round(hit.mean() * 100, 1), len(df)

def run():
    mag7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    data = yf.download(mag7, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in mag7:
        try:
            df = data[s].dropna()
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-MAIN_H) / df["Close"] - 1

            train = df.iloc[:-MAIN_H].dropna()
            model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {"pred": pred, "price": df["Close"].iloc[-1], "sup": sup, "res": res}
        except Exception:
            continue

    hit_rate, n = calc_horizon_hit_rate(HISTORY_FILE, MAIN_H)
    horizon_info = (
        f"🧠 Horizon：{MAIN_H} 日｜命中率：{hit_rate}%（{n} 筆）"
        if hit_rate is not None else
        f"🧠 Horizon：{MAIN_H} 日｜命中率：計算中"
    )

    msg = f"🟢 **SYSTEM MODE：NORMAL**\n{horizon_info}\n\n📊 **美股 AI 預測報告 ({datetime.now():%Y-%m-%d})**\n\n"

    for s, r in results.items():
        msg += f"{s}：`{r['pred']:+.2%}` (支撐 {r['sup']} / 壓力 {r['res']})\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    if not L3_WARNING:
        hist = [{
            "date": datetime.now().date(),
            "symbol": s,
            "entry_price": r["price"],
            "pred_ret": r["pred"],
            "horizon": MAIN_H,
            "settled": False,
        } for s, r in results.items()]

        pd.DataFrame(hist).to_csv(
            HISTORY_FILE,
            mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()
