"""Estrategia: filtro de tendencia EMA9/21 + disparador RSI(14), salidas por ATR."""

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind


@dataclass
class StrategyConfig:
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_trigger: float = 50.0  # cruce de RSI sobre/bajo este nivel dispara la entrada
    atr_period: int = 14
    atr_sl_mult: float = 1.0
    atr_tp_mult: float = 1.5


def compute_indicators(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ind.ema(out["close"], cfg.ema_fast)
    out["ema_slow"] = ind.ema(out["close"], cfg.ema_slow)
    out["rsi"] = ind.rsi(out["close"], cfg.rsi_period)
    out["atr"] = ind.atr(out, cfg.atr_period)
    return out


def signals_from_indicators(data: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """Aplica la logica de señales sobre un DataFrame que ya tiene ema_fast/ema_slow/rsi.

    Tendencia: EMA rapida vs EMA lenta.
    Disparador: cruce del RSI sobre (long) o bajo (short) el nivel `rsi_trigger`,
    solo quedan habilitadas las entradas a favor de la tendencia vigente.
    """
    out = data.copy()

    uptrend = out["ema_fast"] > out["ema_slow"]
    downtrend = out["ema_fast"] < out["ema_slow"]

    rsi_cross_up = (out["rsi"] > cfg.rsi_trigger) & (out["rsi"].shift(1) <= cfg.rsi_trigger)
    rsi_cross_down = (out["rsi"] < cfg.rsi_trigger) & (out["rsi"].shift(1) >= cfg.rsi_trigger)

    out["long_signal"] = uptrend & rsi_cross_up
    out["short_signal"] = downtrend & rsi_cross_down
    return out


def generate_signals(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """Calcula indicadores y marca long_signal/short_signal en la vela de confirmacion."""
    data = compute_indicators(df, cfg)
    return signals_from_indicators(data, cfg)
