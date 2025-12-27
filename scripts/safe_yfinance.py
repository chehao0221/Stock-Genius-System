# scripts/safe_yfinance.py
import yfinance as yf
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

def safe_download(
    tickers,
    period="2y",
    auto_adjust=True,
    group_by="ticker",
):
    try:
        df = yf.download(
            tickers,
            period=period,
            auto_adjust=auto_adjust,
            group_by=group_by,
            progress=False,
            threads=True,
        )

        if df is None or isinstance(df, pd.DataFrame) and df.empty:
            raise ValueError("Yahoo returned empty data")

        return df

    except Exception as e:
        print(f"[WARN] Yahoo Finance unavailable: {e}")
        return None
