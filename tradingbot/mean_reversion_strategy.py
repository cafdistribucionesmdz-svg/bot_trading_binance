"""Estrategia de reversion a la media: Bandas de Bollinger + RSI en extremos.

Hipotesis distinta a la de seguimiento de tendencia: en vez de operar a favor del
movimiento, se apuesta a que un movimiento extremo (precio muy alejado de su media,
con el RSI en sobrecompra/sobreventa) tiende a corregir hacia el precio medio.

Entrada:
- Largo: el precio perfora la banda inferior de Bollinger con RSI en sobreventa, y
  en una vela posterior vuelve a meterse dentro de la banda (confirma el rebote).
- Corto: lo mismo pero en la banda superior con RSI en sobrecompra.

Salida: SL/TP fijados por ATR al momento de la entrada, igual que en las otras
estrategias del proyecto (por defecto el TP es mas chico que el SL, porque los
rebotes de reversion suelen ser movimientos cortos).
"""

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind
from .backtester import BacktestConfig, simulate


@dataclass
class MeanReversionConfig:
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    atr_period: int = 14
    atr_sl_mult: float = 1.5
    atr_tp_mult: float = 1.0


def compute_indicators(df: pd.DataFrame, cfg: MeanReversionConfig) -> pd.DataFrame:
    out = df.copy()
    sma = out["close"].rolling(cfg.bb_period).mean()
    std = out["close"].rolling(cfg.bb_period).std()
    out["bb_mid"] = sma
    out["bb_upper"] = sma + cfg.bb_std * std
    out["bb_lower"] = sma - cfg.bb_std * std
    out["rsi"] = ind.rsi(out["close"], cfg.rsi_period)
    out["atr"] = ind.atr(out, cfg.atr_period)
    return out


def generate_signals(df: pd.DataFrame, cfg: MeanReversionConfig) -> pd.DataFrame:
    out = compute_indicators(df, cfg)

    oversold_extreme = (out["close"] < out["bb_lower"]) & (out["rsi"] < cfg.rsi_oversold)
    overbought_extreme = (out["close"] > out["bb_upper"]) & (out["rsi"] > cfg.rsi_overbought)

    out["long_signal"] = oversold_extreme.shift(1).fillna(False) & (out["close"] >= out["bb_lower"])
    out["short_signal"] = overbought_extreme.shift(1).fillna(False) & (out["close"] <= out["bb_upper"])
    return out


def run_backtest(df: pd.DataFrame, cfg: MeanReversionConfig, bt_cfg: BacktestConfig):
    data = generate_signals(df, cfg)
    return simulate(data, cfg.atr_sl_mult, cfg.atr_tp_mult, bt_cfg)
