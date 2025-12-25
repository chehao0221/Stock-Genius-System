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
# L4 / Observation Flags（只讀）
# ===============================
L4_ACTIVE_FILE = os.getenv(
    "L4_ACTIVE_FILE",
    os.path.join(DATA_DIR, "l4_active.flag")
)
OBS_FLAG_FILE = os.path.join(DATA_DIR, "l4_last_end.flag")

def get_system_mode():
    now = datetime.now().timestamp()

    if os.path.exists(L4_ACTIVE_FILE):
        return "🔴 SYSTEM MODE：L4 ACTIVE"

    if os.path.exists(OBS_FLAG_FILE):
        try:
            last_end = float(open(OBS_FLAG_FILE).read().strip())
            if now - last_end < 86400:
                return "🟠 SYSTEM MODE：OBSERVATION"
        except Exception:
            pass

    return "🟢 SYSTEM MODE：NORMAL"

MODE = get_system_mode()

# 🔴 L4 期間 → 直接中止 AI
if MODE.startswith("🔴"):
    print("🚨 L4 active detected — US AI analysis skipped")
    sys.exit(0)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# ===============================
# Utilities
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
        df = pd.read_html(
            requests.get(url, headers=headers, timeout=10).text
        )[0]
        return [s.replace(".", "-") for s in df["Symbol"]]
    except Exception:
        return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

# ===============================
# 5-Day Settle Report
# ===============================
def get_settle_report():
    if not os.path.exists(HISTORY_FILE):
        return ""

    df = pd.read_csv(HISTORY_FILE)
    unsettled = df[df["settled"] == False]

    if unsettled.empty:
        return ""

    report = "\n🏁 **美股 5 日回測結算**\n"

    for idx, row in unsettled.iterrows():
        try:
            price_df = yf.download(
                row["symbol"],
                period="7d",
                auto_adjust=True,
                progress=False,
            )
            exit_price = price_df["Close"].iloc[-1]
            ret = (exit_price - row["entry_price"]) / row["entry_price"]
            df.at[idx, "settled"] = True

            report += f"• `{row['symbol']}` `{ret:+.2%}`\n"
        except Exception:
            continue

    df.to_csv(HISTORY_FILE, index=False)
    return report

# ===============================
# Main
# ===============================
def run():
    mag_7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    watch = list(dict.fromkeys(mag_7 + get_sp500()))

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
    # Compose Message
    # =========================
    msg = f"{MODE}\n\n📊 **美股 AI 進階預測報告 ({datetime.now():%Y-%m-%d})**\n"
    msg += "------------------------------------------\n\n"

    medals = ["🥇", "🥈", "🥉", "📈", "📈"]
    top_5 = []

    if MODE.endswith("NORMAL"):
        horses = {
            k: v for k, v in results.items()
            if k not in mag_7 and v["pred"] > 0
        }
        top_5 = sorted(
            horses, key=lambda x: horses[x]["pred"], reverse=True
        )[:5]

        msg += "🏆 **AI 海選 Top 5 (潛力股)**\n"
        for i, s in enumerate(top_5):
            r = results[s]
            msg += f"{medals[i]} {s}: `{r['pred']:+.2%}`\n"
    else:
        msg += "⚠️ 觀察期中，暫停海選潛力股\n\n"

    msg += "\n💎 **Magnificent 7 監控 (固定顯示)**\n"
    for s in mag_7:
        if s in results:
            r = results[s]
            msg += f"{s}: `{r['pred']:+.2%}`\n"

    msg += get_settle_report()
    msg += "\n💡 AI 為機率模型，僅供研究參考"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else:
        print(msg)

    # =========================
    # Save History（僅 NORMAL）
    # =========================
    if MODE.endswith("NORMAL"):
        hist = [
            {
                "date": datetime.now().date(),
                "symbol": s,
                "entry_price": results[s]["price"],
                "pred_ret": results[s]["pred"],
                "settled": False,
            }
            for s in (top_5 + mag_7)
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
