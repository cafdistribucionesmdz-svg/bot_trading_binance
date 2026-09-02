"""Descarga velas historicas de un par de Forex desde Yahoo Finance (via yfinance).

No requiere cuenta ni API key. Yahoo Finance limita el intervalo de 1 hora a un
maximo de ~730 dias hacia atras.

Uso:
    python scripts/download_fx_data.py --symbol EURUSD=X --interval 1h --days 730
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yfinance as yf


def main():
    parser = argparse.ArgumentParser(description="Descarga velas historicas de Forex (Yahoo Finance)")
    parser.add_argument("--symbol", default="EURUSD=X", help="Ticker de Yahoo Finance (ej: EURUSD=X)")
    parser.add_argument("--interval", default="1h", help="1h, 1d, etc.")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    clean_name = args.symbol.replace("=X", "").replace("/", "")
    out = args.out or f"data/{clean_name}_{args.interval}.csv"

    df = yf.Ticker(args.symbol).history(period=f"{args.days}d", interval=args.interval)
    if df.empty:
        raise SystemExit(
            "No se recibieron datos. Probá con --days mas chico "
            "(Yahoo Finance limita el intervalo de 1h a unos 730 dias)."
        )

    df = df.rename(
        columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )
    df = df[["open", "high", "low", "close", "volume"]]
    df.index.name = "timestamp"
    df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    df.to_csv(out)
    print(f"Guardadas {len(df)} velas en {out}")


if __name__ == "__main__":
    main()
