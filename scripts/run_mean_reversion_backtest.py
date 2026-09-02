"""Backtest de la estrategia de reversion a la media (Bandas de Bollinger + RSI).

Uso:
    python scripts/run_mean_reversion_backtest.py --data data/BTCUSDT_5m.csv
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tradingbot.backtester import BacktestConfig, compute_stats
from tradingbot.mean_reversion_strategy import MeanReversionConfig, run_backtest


def main():
    parser = argparse.ArgumentParser(description="Backtest de reversion a la media")
    parser.add_argument("--data", required=True)
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--leverage", type=int, default=5)
    args = parser.parse_args()

    df = pd.read_csv(args.data, index_col=0, parse_dates=True)

    strat_cfg = MeanReversionConfig()
    bt_cfg = BacktestConfig(initial_capital=args.capital, risk_pct=args.risk_pct, leverage=args.leverage)

    trades_df, equity_df = run_backtest(df, strat_cfg, bt_cfg)
    stats = compute_stats(trades_df, equity_df, args.capital)

    print("\n== Resultados del backtest (reversion a la media) ==")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if not trades_df.empty:
        out = args.data.replace(".csv", "_mr_trades.csv")
        trades_df.to_csv(out, index=False)
        print(f"\nDetalle de operaciones guardado en {out}")


if __name__ == "__main__":
    main()
