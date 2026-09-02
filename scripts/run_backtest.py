"""Corre el backtest de la estrategia EMA9/21 + RSI(14) + salidas por ATR.

Uso:
    python scripts/run_backtest.py --data data/BTCUSDT_5m.csv
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tradingbot.backtester import BacktestConfig, compute_stats, run_backtest
from tradingbot.strategy import StrategyConfig


def main():
    parser = argparse.ArgumentParser(description="Backtest de la estrategia")
    parser.add_argument("--data", required=True, help="CSV con columnas timestamp,open,high,low,close,volume")
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--leverage", type=int, default=5)
    args = parser.parse_args()

    df = pd.read_csv(args.data, index_col=0, parse_dates=True)

    strat_cfg = StrategyConfig()
    bt_cfg = BacktestConfig(
        initial_capital=args.capital, risk_pct=args.risk_pct, leverage=args.leverage
    )

    trades_df, equity_df = run_backtest(df, strat_cfg, bt_cfg)
    stats = compute_stats(trades_df, equity_df, args.capital)

    print("\n== Resultados del backtest ==")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if not trades_df.empty:
        trades_out = args.data.replace(".csv", "_trades.csv")
        trades_df.to_csv(trades_out, index=False)
        print(f"\nDetalle de operaciones guardado en {trades_out}")


if __name__ == "__main__":
    main()
