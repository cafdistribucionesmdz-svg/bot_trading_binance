"""Estrategia de price action con estructura de mercado.

Replica la logica de un bot armado por fuera de este proyecto:

- Sigue la tendencia mayor: estructura de maximos/minimos crecientes (uptrend)
  o decrecientes (downtrend), a partir de swings tipo fractal. Sin estructura
  clara -> no opera.
- Entra en pullbacks hacia la zona del ultimo swing de soporte (en uptrend) o
  resistencia (en downtrend), confirmados con una vela de price action (pin
  bar o envolvente) a favor de la tendencia.
- SL detras del swing de estructura que origino la señal (con un pequeño
  colchon de ATR). TP inicial a 2R.
- Trailing por etapas: al llegar a +2R, SL a breakeven y TP se extiende a 3R;
  al llegar a +3R, SL asegura +1R y TP se extiende a 4R (tope maximo).

Nota sobre simplificacion: con datos OHLC (sin ticks) no se puede saber el
orden exacto de los eventos dentro de una misma vela. En cada vela primero se
actualiza el escalon de trailing si el rango de esa vela lo alcanza (para que
"llegar a 2R" extienda el objetivo en vez de cerrar en el TP viejo), y recien
con esos niveles ya al dia se chequea si esa misma vela toca el SL o el TP.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from . import indicators as ind
from .backtester import BacktestConfig, Trade
from .risk import cap_position_size, position_size


@dataclass
class PriceActionConfig:
    swing_lookback: int = 2  # velas a cada lado para confirmar un swing (fractal)
    atr_period: int = 14
    pullback_tolerance_atr_mult: float = 0.5
    pin_bar_wick_ratio: float = 0.6  # mecha dominante >= 60% del rango de la vela
    pin_bar_body_ratio: float = 0.35  # cuerpo <= 35% del rango de la vela
    sl_buffer_atr_mult: float = 0.1
    initial_tp_r: float = 2.0
    stage1_trigger_r: float = 2.0
    stage1_sl_r: float = 0.0  # breakeven
    stage1_tp_r: float = 3.0
    stage2_trigger_r: float = 3.0
    stage2_sl_r: float = 1.0
    stage2_tp_r: float = 4.0  # tope maximo


def compute_confirmations(df: pd.DataFrame, cfg: PriceActionConfig) -> pd.DataFrame:
    out = df.copy()
    out["atr"] = ind.atr(out, cfg.atr_period)

    k = cfg.swing_lookback
    window = 2 * k + 1
    out["is_swing_high"] = out["high"] == out["high"].rolling(window, center=True).max()
    out["is_swing_low"] = out["low"] == out["low"].rolling(window, center=True).min()

    body = (out["close"] - out["open"]).abs()
    total_range = (out["high"] - out["low"]).replace(0, np.nan)
    upper_wick = out["high"] - out[["open", "close"]].max(axis=1)
    lower_wick = out[["open", "close"]].min(axis=1) - out["low"]

    bullish_pin = (lower_wick >= cfg.pin_bar_wick_ratio * total_range) & (
        body <= cfg.pin_bar_body_ratio * total_range
    )
    bearish_pin = (upper_wick >= cfg.pin_bar_wick_ratio * total_range) & (
        body <= cfg.pin_bar_body_ratio * total_range
    )

    prev_open = out["open"].shift(1)
    prev_close = out["close"].shift(1)
    prev_bearish = prev_close < prev_open
    prev_bullish = prev_close > prev_open
    cur_bullish = out["close"] > out["open"]
    cur_bearish = out["close"] < out["open"]

    bullish_engulf = prev_bearish & cur_bullish & (out["open"] <= prev_close) & (out["close"] >= prev_open)
    bearish_engulf = prev_bullish & cur_bearish & (out["open"] >= prev_close) & (out["close"] <= prev_open)

    out["bullish_confirmation"] = (bullish_pin | bullish_engulf).fillna(False)
    out["bearish_confirmation"] = (bearish_pin | bearish_engulf).fillna(False)
    return out


def run_backtest(df: pd.DataFrame, cfg: PriceActionConfig, bt_cfg: BacktestConfig):
    data = compute_confirmations(df, cfg)
    n = len(data)

    highs = data["high"].to_numpy()
    lows = data["low"].to_numpy()
    opens = data["open"].to_numpy()
    closes = data["close"].to_numpy()
    atrs = data["atr"].to_numpy()
    is_sw_high = data["is_swing_high"].to_numpy()
    is_sw_low = data["is_swing_low"].to_numpy()
    bull_conf = data["bullish_confirmation"].to_numpy()
    bear_conf = data["bearish_confirmation"].to_numpy()
    index = data.index

    k = cfg.swing_lookback
    swing_highs: list[float] = []
    swing_lows: list[float] = []

    capital = bt_cfg.initial_capital
    equity_curve = []
    trades: list[Trade] = []

    position = None  # dict: trade, r, stage
    pending_entry = None  # (side, sl) confirmado en la vela anterior

    for i in range(n):
        j = i - k
        if j >= 0:
            # se descartan duplicados consecutivos (ej: dos velas empatadas en el mismo
            # extremo) para no romper la comparacion de "maximo/minimo creciente"
            if is_sw_high[j] and (not swing_highs or highs[j] != swing_highs[-1]):
                swing_highs.append(highs[j])
            if is_sw_low[j] and (not swing_lows or lows[j] != swing_lows[-1]):
                swing_lows.append(lows[j])

        ts = index[i]

        if pending_entry is not None and position is None:
            side, sl = pending_entry
            entry_price = opens[i]
            r = (entry_price - sl) if side == "long" else (sl - entry_price)
            if r > 0:
                tp = entry_price + cfg.initial_tp_r * r if side == "long" else entry_price - cfg.initial_tp_r * r
                qty = position_size(capital, entry_price, sl, bt_cfg.risk_pct)
                qty = cap_position_size(qty, entry_price, capital, bt_cfg.leverage)
                if qty > 0:
                    position = {
                        "trade": Trade(side=side, entry_time=ts, entry_price=entry_price, qty=qty, sl=sl, tp=tp),
                        "r": r,
                        "stage": 0,
                    }
        pending_entry = None

        if position is not None:
            trade: Trade = position["trade"]
            r = position["r"]
            stage = position["stage"]

            # 1) progresion de etapas primero (con el rango de ESTA vela): si la vela
            # alcanza un nuevo escalon, el SL/TP se actualiza antes de chequear la
            # salida, para que "llegar a 2R" extienda el TP en vez de cerrar en el
            # objetivo viejo.
            favorable = (highs[i] - trade.entry_price) / r if trade.side == "long" else (
                trade.entry_price - lows[i]
            ) / r

            if stage < 2 and favorable >= cfg.stage2_trigger_r:
                stage = 2
                if trade.side == "long":
                    trade.sl = trade.entry_price + cfg.stage2_sl_r * r
                    trade.tp = trade.entry_price + cfg.stage2_tp_r * r
                else:
                    trade.sl = trade.entry_price - cfg.stage2_sl_r * r
                    trade.tp = trade.entry_price - cfg.stage2_tp_r * r
            elif stage < 1 and favorable >= cfg.stage1_trigger_r:
                stage = 1
                if trade.side == "long":
                    trade.sl = trade.entry_price + cfg.stage1_sl_r * r
                    trade.tp = trade.entry_price + cfg.stage1_tp_r * r
                else:
                    trade.sl = trade.entry_price - cfg.stage1_sl_r * r
                    trade.tp = trade.entry_price - cfg.stage1_tp_r * r
            position["stage"] = stage

            # 2) recien ahora se chequea la salida, con los niveles ya al dia
            if trade.side == "long":
                hit_sl = lows[i] <= trade.sl
                hit_tp = highs[i] >= trade.tp
            else:
                hit_sl = highs[i] >= trade.sl
                hit_tp = lows[i] <= trade.tp

            exit_price = None
            reason = ""
            if hit_sl:
                exit_price, reason = trade.sl, "SL"
            elif hit_tp:
                exit_price, reason = trade.tp, "TP"

            if exit_price is not None:
                direction = 1 if trade.side == "long" else -1
                gross_pnl = direction * (exit_price - trade.entry_price) * trade.qty
                fees = (trade.entry_price + exit_price) * trade.qty * bt_cfg.taker_fee
                pnl = gross_pnl - fees
                capital += pnl
                trade.exit_time = ts
                trade.exit_price = exit_price
                trade.pnl = pnl
                trade.exit_reason = reason
                trades.append(trade)
                position = None

        if position is None and len(swing_highs) >= 2 and len(swing_lows) >= 2 and not pd.isna(atrs[i]):
            uptrend = swing_highs[-1] > swing_highs[-2] and swing_lows[-1] > swing_lows[-2]
            downtrend = swing_highs[-1] < swing_highs[-2] and swing_lows[-1] < swing_lows[-2]
            tolerance = cfg.pullback_tolerance_atr_mult * atrs[i]

            if uptrend and bull_conf[i] and abs(lows[i] - swing_lows[-1]) <= tolerance:
                sl = swing_lows[-1] - cfg.sl_buffer_atr_mult * atrs[i]
                pending_entry = ("long", sl)
            elif downtrend and bear_conf[i] and abs(highs[i] - swing_highs[-1]) <= tolerance:
                sl = swing_highs[-1] + cfg.sl_buffer_atr_mult * atrs[i]
                pending_entry = ("short", sl)

        equity_curve.append((ts, capital))

    equity_df = pd.DataFrame(equity_curve, columns=["time", "equity"]).set_index("time")
    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    return trades_df, equity_df
