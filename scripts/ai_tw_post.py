import os, sys, warnings, requests
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

if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — TW AI skipped")
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_TW", "").strip()

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

def pred_icon(pred):
    return "🟢" if pred > 0 else "⚪"

# ===============================
# Main
# ===============================
def run():
    watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]

    data = yf.download(
        watch, period="2y", auto_adjust=True, group_by="ticker", progress=False
    )

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": df["Close"].iloc[-1],
                "sup": sup,
                "res": res,
            }
        except Exception:
            continue

    # ===============================
    # Discord Message
    # ===============================
    mode = "🟡 **SYSTEM MODE：RISK WARNING (L3)**" if L3_WARNING else "🟢 **SYSTEM MODE：NORMAL**"
    msg = f"{mode}\n\n📊 **台股 AI 預測報告 ({datetime.now():%Y-%m-%d})**\n\n"

    ranked = sorted(results.items(), key=lambda x: x[1]["pred"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]

    for i, (s, r) in enumerate(ranked):
        medal = medals[i] if i < 3 else ""
        icon = pred_icon(r["pred"])
        msg += f"{medal} **{s}**\n"
        msg += f"📈 預估 `{r['pred']:+.2%}` {icon}\n"
        msg += f"支撐 `{r['sup']}` / 壓力 `{r['res']}`\n\n"

    msg += "⚠️ 模型為機率推估，僅供研究參考，非投資建議。"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    # 僅 NORMAL 寫歷史（原邏輯不動）
    if not L3_WARNING:
        hist = [{
            "date": datetime.now().date(),
            "symbol": s,
            "entry_price": r["price"],
            "pred_ret": r["pred"],
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
