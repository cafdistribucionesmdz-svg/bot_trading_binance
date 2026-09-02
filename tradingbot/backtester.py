"""Backtester simple, posicion unica a la vez, salidas por SL/TP basados en ATR."""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .risk import cap_position_size, position_size
from .strategy import StrategyConfig, generate_signals


@dataclass
class BacktestConfig:
    initial_capital: float = 1000.0
    risk_pct: float = 0.01
    leverage: int = 5
    taker_fee: float = 0.0004  # comision taker de Binance Futures (~0.04%)


@dataclass
class Trade:
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    qty: float
    sl: float
    tp: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    exit_reason: str = ""


def simulate(data: pd.DataFrame, atr_sl_mult: float, atr_tp_mult: float, bt_cfg: BacktestConfig):
    """Simula sobre un DataFrame que ya tiene las columnas long_signal/short_signal/atr.

    La entrada se ejecuta en la apertura de la vela siguiente a la señal, con SL/TP
    calculados a partir del ATR de la vela donde se confirmo la señal. Si en la misma
    vela se tocan SL y TP se asume el peor caso (sale por SL).
    """
    capital = bt_cfg.initial_capital
    equity_curve = []
    trades: list[Trade] = []
    position: Optional[Trade] = None

    for i in range(1, len(data)):
        row = data.iloc[i]
        prev = data.iloc[i - 1]
        ts = data.index[i]

        if position is not None:
            if position.side == "long":
                hit_sl = row["low"] <= position.sl
                hit_tp = row["high"] >= position.tp
            else:
                hit_sl = row["high"] >= position.sl
                hit_tp = row["low"] <= position.tp

            exit_price = None
            reason = ""
            if hit_sl:
                exit_price, reason = position.sl, "SL"
            elif hit_tp:
                exit_price, reason = position.tp, "TP"

            if exit_price is not None:
                direction = 1 if position.side == "long" else -1
                gross_pnl = direction * (exit_price - position.entry_price) * position.qty
                fees = (position.entry_price + exit_price) * position.qty * bt_cfg.taker_fee
                pnl = gross_pnl - fees

                capital += pnl
                position.exit_time = ts
                position.exit_price = exit_price
                position.pnl = pnl
                position.exit_reason = reason
                trades.append(position)
                position = None

        if position is None and (prev["long_signal"] or prev["short_signal"]):
            atr_val = prev["atr"]
            entry_price = row["open"]

            if pd.isna(atr_val) or atr_val <= 0:
                equity_curve.append((ts, capital))
                continue

            side = "long" if prev["long_signal"] else "short"
            if side == "long":
                sl = entry_price - atr_sl_mult * atr_val
                tp = entry_price + atr_tp_mult * atr_val
            else:
                sl = entry_price + atr_sl_mult * atr_val
                tp = entry_price - atr_tp_mult * atr_val

            qty = position_size(capital, entry_price, sl, bt_cfg.risk_pct)
            qty = cap_position_size(qty, entry_price, capital, bt_cfg.leverage)

            if qty > 0:
                position = Trade(
                    side=side, entry_time=ts, entry_price=entry_price, qty=qty, sl=sl, tp=tp
                )

        equity_curve.append((ts, capital))

    equity_df = pd.DataFrame(equity_curve, columns=["time", "equity"]).set_index("time")
    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    return trades_df, equity_df


def run_backtest(df: pd.DataFrame, strat_cfg: StrategyConfig, bt_cfg: BacktestConfig):
    """Genera las señales de la estrategia de un solo timeframe y las simula."""
    data = generate_signals(df, strat_cfg)
    return simulate(data, strat_cfg.atr_sl_mult, strat_cfg.atr_tp_mult, bt_cfg)


def compute_stats(trades_df: pd.DataFrame, equity_df: pd.DataFrame, initial_capital: float) -> dict:
    if trades_df.empty:
        return {"trades": 0, "total_return_pct": 0.0}

    wins = trades_df[trades_df["pnl"] > 0]
    losses = trades_df[trades_df["pnl"] <= 0]
    gross_profit = wins["pnl"].sum()
    gross_loss = -losses["pnl"].sum()

    final_equity = equity_df["equity"].iloc[-1] if not equity_df.empty else initial_capital
    running_max = equity_df["equity"].cummax()
    drawdown = (equity_df["equity"] - running_max) / running_max

    return {
        "trades": len(trades_df),
        "win_rate_pct": round(100 * len(wins) / len(trades_df), 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "total_return_pct": round(100 * (final_equity - initial_capital) / initial_capital, 2),
        "max_drawdown_pct": round(100 * drawdown.min(), 2),
        "final_equity": round(final_equity, 2),
    }
