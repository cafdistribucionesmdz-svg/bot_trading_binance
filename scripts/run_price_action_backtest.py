"""Backtest de la estrategia de price action (estructura + pullback + trailing por R).

Uso:
    python scripts/run_price_action_backtest.py --data data/EURUSD_m15.csv
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tradingbot.backtester import BacktestConfig, compute_stats
from tradingbot.price_action_strategy import PriceActionConfig, run_backtest


def main():
    parser = argparse.ArgumentParser(description="Backtest de la estrategia de price action")
    parser.add_argument("--data", required=True)
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--leverage", type=int, default=10)
    parser.add_argument("--taker-fee", type=float, default=0.00005, help="Costo aproximado (spread) por lado")
    args = parser.parse_args()

    df = pd.read_csv(args.data, index_col=0, parse_dates=True)

    strat_cfg = PriceActionConfig()
    bt_cfg = BacktestConfig(
        initial_capital=args.capital, risk_pct=args.risk_pct, leverage=args.leverage, taker_fee=args.taker_fee
    )

    trades_df, equity_df = run_backtest(df, strat_cfg, bt_cfg)
    stats = compute_stats(trades_df, equity_df, args.capital)

    print("\n== Resultados del backtest (price action / estructura) ==")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if not trades_df.empty:
        out = args.data.replace(".csv", "_pa_trades.csv")
        trades_df.to_csv(out, index=False)
        print(f"\nDetalle de operaciones guardado en {out}")


if __name__ == "__main__":
    main()
