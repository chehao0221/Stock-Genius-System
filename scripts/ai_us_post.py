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

if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — US AI skipped")
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")

WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_US")
    or os.getenv("DISCORD_WEBHOOK_URL", "")
).strip()

# 🧠 Horizon 設定（與台股一致）
HORIZONS = [3, 5, 10]
MAIN_H = 3 if L3_WARNING else 5

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
        df = pd.read_html(
            requests.get(url, headers=headers, timeout=10).text
        )[0]
        return [s.replace(".", "-") for s in df["Symbol"]]
    except Exception:
        return []

def settle_history(price_data):
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

        symbol = r["symbol"]
        horizon = int(r.get("horizon", 5))
        entry_date = pd.to_datetime(r["date"])

        if symbol not in price_data:
            continue

        df = price_data[symbol]
        future = df[df.index >= entry_date]

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
    mag7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

    watch = mag7 if L3_WARNING else list(dict.fromkeys(mag7 + get_sp500()))

    data = yf.download(
        watch,
        period="2y",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
    )

    # 🔁 自動結算歷史績效
    settle_history(data)

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

            preds = {}
            for h in HORIZONS:
                df["target"] = df["Close"].shift(-h) / df["Close"] - 1
                train = df.iloc[:-h].dropna()

                model = XGBRegressor(
                    n_estimators=120,
                    max_depth=3,
                    learning_rate=0.05,
                    random_state=42,
                )
                model.fit(train[feats], train["target"])
                preds[h] = float(model.predict(df[feats].iloc[-1:])[0])

            sup, res = calc_pivot(df)
            results[s] = {
                "price": round(df["Close"].iloc[-1], 2),
                "preds": preds,
                "sup": sup,
                "res": res,
            }
        except Exception:
            continue

    mode = (
        "🟡 **SYSTEM MODE：RISK WARNING (L3)**"
        if L3_WARNING
        else "🟢 **SYSTEM MODE：NORMAL**"
    )

    msg = f"{mode}\n\n📊 **美股 AI 預測報告 ({datetime.now():%Y-%m-%d})**\n"
    msg += "------------------------------------------\n\n"

    medals = ["🥇", "🥈", "🥉", "📈", "📈"]

    top_5 = []
    if not L3_WARNING:
        horses = {
            k: v for k, v in results.items()
            if k not in mag7 and v["preds"][MAIN_H] > 0
        }
        top_5 = sorted(
            horses,
            key=lambda x: horses[x]["preds"][MAIN_H],
            reverse=True,
        )[:5]

        msg += "🏆 **AI 海選 Top 5（主 Horizon）**\n"
        for i, s in enumerate(top_5):
            r = results[s]
            p = r["preds"][MAIN_H]
            msg += f"{medals[i]} {s}: `{p:+.2%}`（{MAIN_H}日）\n"
            msg += (
                f" └ 現價 `{r['price']}` "
                f"(支撐 `{r['sup']}` / 壓力 `{r['res']}`)\n"
            )
        msg += "\n"
    else:
        msg += "⚠️ L3 觀察期，暫停潛力股海選\n\n"

    msg += "💎 **Magnificent 7（固定監控）**\n"
    for s in mag7:
        if s in results:
            r = results[s]
            p = r["preds"][MAIN_H]
            msg += f"{s}: `{p:+.2%}`（{MAIN_H}日）\n"
            msg += (
                f" └ 現價 `{r['price']}` "
                f"(支撐 `{r['sup']}` / 壓力 `{r['res']}`)\n"
            )

    msg += "\n💡 AI 為機率模型，僅供研究參考"

    if WEBHOOK_URL:
        requests.post(
            WEBHOOK_URL,
            json={"content": msg[:1900]},
            timeout=15,
        )
    else:
        print(msg)

    # 📝 寫入歷史（僅 NORMAL）
    if not L3_WARNING:
        rows = []
        for s in (top_5 + mag7):
            if s in results:
                rows.append({
                    "date": datetime.now().date(),
                    "symbol": s,
                    "entry_price": results[s]["price"],
                    "pred_ret": results[s]["preds"][MAIN_H],
                    "horizon": MAIN_H,
                    "settled": False,
                })

        if rows:
            pd.DataFrame(rows).to_csv(
                HISTORY_FILE,
                mode="a",
                header=not os.path.exists(HISTORY_FILE),
                index=False,
            )

if __name__ == "__main__":
    run()
