"""Descarga velas historicas publicas de Binance Futures y las guarda en CSV.

Uso:
    python scripts/download_data.py --symbol BTC/USDT --timeframe 5m --days 90
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tradingbot.data import fetch_ohlcv


def main():
    parser = argparse.ArgumentParser(description="Descarga velas historicas de Binance Futures")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out = args.out or f"data/{args.symbol.replace('/', '')}_{args.timeframe}.csv"

    since_ms = int((pd.Timestamp.utcnow() - pd.Timedelta(days=args.days)).timestamp() * 1000)
    df = fetch_ohlcv(args.symbol, args.timeframe, since_ms)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out)
    print(f"Guardadas {len(df)} velas en {out}")


if __name__ == "__main__":
    main()
