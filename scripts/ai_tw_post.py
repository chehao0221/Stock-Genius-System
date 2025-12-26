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

# ===============================
# Main
# ===============================
def run():
    watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW"]

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

            results[s] = {"pred": pred, "price": df["Close"].iloc[-1], "sup": sup, "res": res}
        except Exception:
            continue

    # ===============================
    # Discord Embed
    # ===============================
    sorted_syms = sorted(results, key=lambda x: results[x]["pred"], reverse=True)
    medals = {sorted_syms[i]: m for i, m in enumerate(["🥇", "🥈", "🥉"]) if i < len(sorted_syms)}

    color = 0xF1C40F if L3_WARNING else 0x2ECC71
    embed = {
        "title": "📊 台股 AI 5 日預測報告",
        "description": f"📅 {datetime.now():%Y-%m-%d}\n"
                       f"{'🟡 系統進入風險觀察期 (L3)' if L3_WARNING else '🟢 系統正常運作'}",
        "color": color,
        "fields": [],
        "footer": {"text": "AI 為機率模型，僅供研究參考"},
    }

    for s in sorted_syms:
        r = results[s]
        emoji = "📈" if r["pred"] > 0 else "📉"
        medal = medals.get(s, "")
        embed["fields"].append({
            "name": f"{medal} {s}",
            "value": f"{emoji} 預估 **{r['pred']:+.2%}**\n支撐 `{r['sup']}` / 壓力 `{r['res']}`",
            "inline": True,
        })

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)

    # ===============================
    # Save History (NORMAL only)
    # ===============================
    if not L3_WARNING:
        pd.DataFrame([
            {
                "date": datetime.now().date(),
                "symbol": s,
                "entry_price": results[s]["price"],
                "pred_ret": results[s]["pred"],
                "settled": False,
            } for s in results
        ]).to_csv(HISTORY_FILE, mode="a", header=not os.path.exists(HISTORY_FILE), index=False)

if __name__ == "__main__":
    run()
