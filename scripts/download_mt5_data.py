"""Descarga velas historicas directamente desde una terminal de MetaTrader 5 local.

Requiere que MetaTrader 5 este INSTALADO y ABIERTO en esta misma computadora,
con sesion iniciada en alguna cuenta (alcanza con una cuenta demo).

Instalacion (solo Windows, la libreria se conecta a la terminal de MT5 local):
    pip install MetaTrader5

Uso:
    python scripts\\download_mt5_data.py --symbol EURUSD --timeframe H1 --days 730
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    raise SystemExit(
        "Falta instalar la libreria de MetaTrader5. Corré: pip install MetaTrader5\n"
        "(Solo funciona en Windows, y necesita la terminal de MT5 abierta en esta compu.)"
    )

TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


def main():
    parser = argparse.ArgumentParser(description="Descarga velas historicas desde MetaTrader 5")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="H1", choices=TIMEFRAMES.keys())
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out = args.out or f"data/{args.symbol}_{args.timeframe.lower()}.csv"

    if not mt5.initialize():
        raise SystemExit(
            f"No se pudo conectar a MetaTrader 5 (error: {mt5.last_error()}).\n"
            "Verificá que la terminal de MT5 este abierta y con sesion iniciada."
        )

    if not mt5.symbol_select(args.symbol, True):
        mt5.shutdown()
        raise SystemExit(
            f"El simbolo '{args.symbol}' no esta disponible en tu bróker. "
            "Revisá el nombre exacto en el Market Watch de MT5 (a veces lleva sufijo, ej: EURUSD.a)."
        )

    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=args.days)
    timeframe_const = getattr(mt5, TIMEFRAMES[args.timeframe])

    rates = mt5.copy_rates_range(args.symbol, timeframe_const, utc_from, utc_to)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        raise SystemExit(
            "No se recibio ningun dato. Es comun que el bróker no tenga tanto historial "
            "cacheado localmente todavia: abrí el grafico de ese simbolo/timeframe en MT5 "
            "y scrolleá bien hacia atras (eso fuerza a MT5 a pedirle mas historial al servidor "
            "del bróker), despues volvé a correr este script."
        )

    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].set_index("timestamp")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    df.to_csv(out)
    print(f"Guardadas {len(df)} velas en {out}")
    print(f"Rango: {df.index[0]} -> {df.index[-1]}")


if __name__ == "__main__":
    main()
