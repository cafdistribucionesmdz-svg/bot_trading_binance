"""Descarga de velas historicas publicas de Binance Futures (no requiere API key)."""

import time

import ccxt
import pandas as pd


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    since_ms: int,
    limit_per_call: int = 1000,
    exchange_id: str = "binanceusdm",
) -> pd.DataFrame:
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})

    all_candles: list = []
    since = since_ms
    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit_per_call)
        if not candles:
            break
        all_candles += candles
        last_ts = candles[-1][0]
        if last_ts == since:
            break
        since = last_ts + 1
        if len(candles) < limit_per_call:
            break
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").set_index("timestamp")
    return df
