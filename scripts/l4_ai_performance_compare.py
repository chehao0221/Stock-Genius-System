import os
import pandas as pd
import yfinance as yf
import datetime
import requests

# ===============================
# Base
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

TW_HISTORY = os.path.join(DATA_DIR, "tw_history.csv")
US_HISTORY = os.path.join(DATA_DIR, "us_history.csv")
BLACK_SWAN = os.path.join(DATA_DIR, "black_swan_history.csv")

OUTPUT = os.path.join(DATA_DIR, "l4_ai_performance_compare.csv")

DISCORD_WEBHOOK_URL = os.getenv("BLACK_SWAN_WEBHOOK_URL", "").strip()

LOOKBACK_DAYS = 5
LOOKFORWARD_DAYS = 5

# ===============================
# Utils
# ===============================
def calc_return(symbol, start_date, days):
    try:
        df = yf.download(
            symbol,
            start=start_date,
            end=start_date + datetime.timedelta(days=days + 3),
            auto_adjust=True,
            progress=False,
        )
        if len(df) < days + 1:
            return None
        return (df["Close"].iloc[days] - df["Close"].iloc[0]) / df["Close"].iloc[0]
    except:
        return None

# ===============================
# Main
# ===============================
def run():
    if not os.path.exists(BLACK_SWAN):
        print("No black swan history")
        return

    bs = pd.read_csv(BLACK_SWAN)
    bs = bs[bs["level"] == 4]

    if bs.empty:
        print("No L4 events found")
        return

    ai_hist = []
    for f in [TW_HISTORY, US_HISTORY]:
        if os.path.exists(f):
            df = pd.read_csv(f)
            ai_hist.append(df)

    ai = pd.concat(ai_hist, ignore_index=True)
    ai["date"] = pd.to_datetime(ai["date"])

    rows = []

    for _, row in bs.iterrows():
        l4_time = pd.to_datetime(row["datetime"])
        l4_date = l4_time.date()

        before = ai[
            (ai["date"] >= l4_date - datetime.timedelta(days=LOOKBACK_DAYS))
            & (ai["date"] < l4_date)
        ]

        after = ai[
            (ai["date"] > l4_date)
            & (ai["date"] <= l4_date + datetime.timedelta(days=LOOKFORWARD_DAYS))
        ]

        # 正常 AI 報酬
        normal_ret = before["pred_ret"].mean() if not before.empty else None

        # 假設 L4 後繼續 AI
        sim_rets = []
        for _, r in after.iterrows():
            ret = calc_return(
                r["symbol"],
                pd.to_datetime(r["date"]),
                LOOKFORWARD_DAYS,
            )
            if ret is not None:
                sim_rets.append(ret)

        simulated_ret = sum(sim_rets) / len(sim_rets) if sim_rets else None

        rows.append({
            "l4_datetime": row["datetime"],
            "market": row["market"],
            "normal_ai_avg_pred": round(normal_ret, 4) if normal_ret else None,
            "simulated_ai_return_if_continue": round(simulated_ret, 4) if simulated_ret else None,
            "ai_paused": True,
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT, index=False)

    # ===============================
    # Discord Report
    # ===============================
    if DISCORD_WEBHOOK_URL and not out.empty:
        msg = "📉 **L4 黑天鵝 × AI 風控績效比較**\n\n"
        for _, r in out.iterrows():
            msg += (
                f"🕒 {r['l4_datetime']} ({r['market']})\n"
                f"🟢 正常期 AI 預測均值：{r['normal_ai_avg_pred']}\n"
                f"🔴 若 L4 後繼續 AI：{r['simulated_ai_return_if_continue']}\n"
                f"🛑 實際策略：停止 AI\n\n"
            )

        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": msg[:1900]},
            timeout=15,
        )

    print("✅ L4 AI performance comparison saved →", OUTPUT)

if __name__ == "__main__":
    run()
