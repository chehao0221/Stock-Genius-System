import yfinance as yf
from datetime import datetime, timedelta

def is_market_open(market: str) -> bool:
    """
    market: "TW" or "US"
    回傳：
    - True  → 交易日
    - False → 假日 / 節日
    """

    symbol = "^TWII" if market == "TW" else "^GSPC"

    try:
        df = yf.download(
            symbol,
            period="5d",
            progress=False,
            auto_adjust=True
        )

        if df.empty:
            return False

        last_date = df.index[-1].date()
        today = datetime.utcnow().date()

        # 台股是 UTC+8，美股是 UTC-5~-4，允許 1 天誤差
        return abs((today - last_date).days) <= 1

    except Exception as e:
        print(f"⚠️ 無法判斷 {market} 是否開盤：{e}")
        return False
