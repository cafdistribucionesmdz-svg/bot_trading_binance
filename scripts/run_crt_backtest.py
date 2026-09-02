"""Backtest de la estrategia CRT (Candle Range Theory).

Usa una vela de un timeframe mayor (por defecto diaria) como "rango", y un
timeframe menor (por defecto 1h) para detectar la barrida de liquidez y la
reversion. El timeframe mayor se arma automaticamente comprimiendo el CSV que
le pases (no hace falta descargarlo aparte).

Uso:
    python scripts/run_crt_backtest.py --data data/BTCUSDT_1h_full.csv
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tradingbot.backtester import BacktestConfig, compute_stats, simulate_with_levels
from tradingbot.crt_strategy import CRTConfig, generate_crt_signals, resample_htf


def main():
    parser = argparse.ArgumentParser(description="Backtest de la estrategia CRT")
    parser.add_argument("--data", required=True, help="CSV del timeframe menor (ej: 1h)")
    parser.add_argument("--htf-rule", default="1D", help="Regla de resample para el rango mayor (ej: 1D, 1W, 4h)")
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--leverage", type=int, default=5)
    args = parser.parse_args()

    ltf_df = pd.read_csv(args.data, index_col=0, parse_dates=True)

    strat_cfg = CRTConfig(htf_rule=args.htf_rule)
    htf_df = resample_htf(ltf_df, strat_cfg.htf_rule)
    bt_cfg = BacktestConfig(initial_capital=args.capital, risk_pct=args.risk_pct, leverage=args.leverage)

    data = generate_crt_signals(ltf_df, htf_df, strat_cfg)
    trades_df, equity_df = simulate_with_levels(data, bt_cfg)
    stats = compute_stats(trades_df, equity_df, args.capital)

    print("\n== Resultados del backtest (CRT) ==")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if not trades_df.empty:
        out = args.data.replace(".csv", "_crt_trades.csv")
        trades_df.to_csv(out, index=False)
        print(f"\nDetalle de operaciones guardado en {out}")


if __name__ == "__main__":
    main()
