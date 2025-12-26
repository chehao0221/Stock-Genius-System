import os
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

OUT_FILE = os.path.join(DATA_DIR, "forecast_observation.csv")

def settle(history_path: str, market: str):
    if not os.path.exists(history_path):
        return

    df = pd.read_csv(history_path)
    if "settled" not in df.columns:
        return

    pending = df[df["settled"] == False]
    if pending.empty:
        return

    rows = []
    for _, r in pending.iterrows():
        symbol = r["symbol"]
        entry_date = pd.to_datetime(r["date"])
        horizon = int(r.get("horizon", 5))
        settle_date = entry_date + timedelta(days=horizon)

        try:
            px = yf.download(
                symbol,
                start=entry_date.strftime("%Y-%m-%d"),
                end=(settle_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )["Close"]

            if len(px) < 2:
                continue

            real_ret = px.iloc[-1] / px.iloc[0] - 1
            hit = int(real_ret > 0)

            rows.append({
                "market": market,
                "symbol": symbol,
                "horizon": horizon,
                "forecast_ret": r["pred_ret"],
                "real_ret": round(real_ret, 4),
                "hit": hit,
                "settle_date": settle_date.date(),
            })

            df.loc[_,"settled"] = True
            df.loc[_,"real_ret"] = round(real_ret, 4)
            df.loc[_,"hit"] = hit

        except Exception:
            continue

    if rows:
        pd.DataFrame(rows).to_csv(
            OUT_FILE,
            mode="a",
            header=not os.path.exists(OUT_FILE),
            index=False,
        )
        df.to_csv(history_path, index=False)

def main():
    settle(os.path.join(DATA_DIR, "tw_history.csv"), "TW")
    settle(os.path.join(DATA_DIR, "us_history.csv"), "US")

if __name__ == "__main__":
    main()
