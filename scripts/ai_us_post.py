import os
import sys
import warnings
import requests
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
# 🔴 L4 / 🟡 L3 FLAGS
# ===============================
L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
L3_WARNING_FILE = os.path.join(DATA_DIR, "l3_warning.flag")

# 🔴 L4 → 直接停機
if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — US AI analysis skipped")
    sys.exit(0)

# 🟡 L3 → 降速模式
L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

def get_sp500():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url, headers=headers, timeout=10).text)[0]
        return [s.replace(".", "-") for s in df["Symbol"]]
    except Exception:
        return []

# ===============================
# Main
# ===============================
def run():
    mag7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

    # 🟡 L3：只跑固定股
    watch = mag7 if L3_WARNING else list(dict.fromkeys(mag7 + get_sp500()))

    data = yf.download(
        watch,
        period="2y",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
    )

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (
                df["Close"] - df["Close"].rolling(20).mean()
            ) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.05,
                random_state=42,
            )
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": round(df["Close"].iloc[-1], 2),
                "sup": sup,
                "res": res,
            }
        except Exception:
            continue

    # =========================
    # Message Compose
    # =========================
    mode = (
        "🟡 **SYSTEM MODE：RISK WARNING (L3)**"
        if L3_WARNING
        else "🟢 **SYSTEM MODE：NORMAL**"
    )

    msg = f"{mode}\n\n📊 **美股 AI 進階預測報告 ({datetime.now():%Y-%m-%d})**\n"
    msg += "------------------------------------------\n\n"

    medals = ["🥇", "🥈", "🥉", "📈", "📈"]

    # 🟢 正常模式才有 Top 5
    top_5 = []
    if not L3_WARNING:
        horses = {k: v for k, v in results.items() if k not in mag7 and v["pred"] > 0}
        top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

        msg += "🏆 **AI 海選 Top 5 (潛力股)**\n"
        for i, s in enumerate(top_5):
            r = results[s]
            msg += f"{medals[i]} {s}: 預估 `{r['pred']:+.2%}`\n"
            msg += f" └ 現價: `{r['price']:.2f}` (支撐: `{r['sup']}` / 壓力: `{r['res']}`)\n"
        msg += "\n"
    else:
        msg += "⚠️ 觀察 / 預警期中，暫停 AI 海選潛力股\n\n"

    # Magnificent 7 永遠顯示
    msg += "💎 **Magnificent 7 監控 (固定顯示)**\n"
    for s in mag7:
        if s in results:
            r = results[s]
            msg += f"{s}: 預估 `{r['pred']:+.2%}`\n"
            msg += f" └ 現價: `{r['price']:.2f}` (支撐: `{r['sup']}` / 壓力: `{r['res']}`)\n"

    msg += "\n💡 AI 為機率模型，僅供研究參考"

    # =========================
    # Send
    # =========================
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else:
        print(msg)

    # =========================
    # Save History（僅 NORMAL）
    # =========================
    if not L3_WARNING:
        hist = [
            {
                "date": datetime.now().date(),
                "symbol": s,
                "entry_price": results[s]["price"],
                "pred_ret": results[s]["pred"],
                "settled": False,
            }
            for s in (top_5 + mag7)
            if s in results
        ]

        if hist:
            pd.DataFrame(hist).to_csv(
                HISTORY_FILE,
                mode="a",
                header=not os.path.exists(HISTORY_FILE),
                index=False,
            )

if __name__ == "__main__":
    run()
