"""Backtest de la estrategia multi-timeframe: sesgo de tendencia en 1H (o el timeframe
mayor que le pases) + cruce de EMA9/21 en un timeframe menor (5m, 1m, etc).

Uso:
    python scripts/run_mtf_backtest.py --htf-data data/BTCUSDT_1h.csv --ltf-data data/BTCUSDT_5m.csv
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tradingbot.backtester import BacktestConfig, compute_stats, simulate
from tradingbot.mtf_strategy import MTFStrategyConfig, generate_mtf_signals


def main():
    parser = argparse.ArgumentParser(description="Backtest de la estrategia multi-timeframe")
    parser.add_argument("--htf-data", required=True, help="CSV del timeframe mayor (ej: 1h)")
    parser.add_argument("--ltf-data", required=True, help="CSV del timeframe menor (ej: 5m o 1m)")
    parser.add_argument("--htf-ma-period", type=int, default=50)
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--leverage", type=int, default=5)
    args = parser.parse_args()

    htf_df = pd.read_csv(args.htf_data, index_col=0, parse_dates=True)
    ltf_df = pd.read_csv(args.ltf_data, index_col=0, parse_dates=True)

    strat_cfg = MTFStrategyConfig(htf_ma_period=args.htf_ma_period)
    bt_cfg = BacktestConfig(initial_capital=args.capital, risk_pct=args.risk_pct, leverage=args.leverage)

    data = generate_mtf_signals(ltf_df, htf_df, strat_cfg)
    trades_df, equity_df = simulate(data, strat_cfg.atr_sl_mult, strat_cfg.atr_tp_mult, bt_cfg)
    stats = compute_stats(trades_df, equity_df, args.capital)

    print("\n== Resultados del backtest multi-timeframe ==")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if not trades_df.empty:
        out = args.ltf_data.replace(".csv", "_mtf_trades.csv")
        trades_df.to_csv(out, index=False)
        print(f"\nDetalle de operaciones guardado en {out}")


if __name__ == "__main__":
    main()
