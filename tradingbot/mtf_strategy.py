"""Estrategia multi-timeframe.

Sesgo de tendencia en un timeframe mayor (1H): precio de cierre por encima/debajo de
una media movil -> solo se habilitan largos/cortos en esa direccion.
Disparador de entrada en un timeframe menor (5m o 1m): cruce de EMA9/21, tomado
solo cuando coincide con el sesgo del timeframe mayor.
SL/TP: ATR del timeframe menor, igual que en la estrategia de un solo timeframe.
"""

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind


@dataclass
class MTFStrategyConfig:
    htf_ma_period: int = 50
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    atr_sl_mult: float = 1.0
    atr_tp_mult: float = 1.5


def htf_bias(htf_df: pd.DataFrame, ma_period: int) -> pd.Series:
    """'long' si el cierre esta por encima de la media movil, 'short' si esta por debajo."""
    ma = ind.ema(htf_df["close"], ma_period)
    bias = pd.Series(index=htf_df.index, dtype=object)
    bias[htf_df["close"] > ma] = "long"
    bias[htf_df["close"] < ma] = "short"
    return bias


def generate_mtf_signals(ltf_df: pd.DataFrame, htf_df: pd.DataFrame, cfg: MTFStrategyConfig) -> pd.DataFrame:
    """Alinea el sesgo del timeframe mayor sobre las velas del timeframe menor y dispara
    la entrada en el cruce de EMA9/21 del timeframe menor, a favor de ese sesgo.

    Importante: se usa el sesgo de la ULTIMA vela del timeframe mayor ya cerrada (shift(1)),
    nunca el de la vela en curso, para no introducir look-ahead bias en el backtest.
    """
    bias = htf_bias(htf_df, cfg.htf_ma_period).shift(1)
    bias_df = bias.rename("htf_bias").to_frame()

    out = ltf_df.copy().sort_index()
    out["ema_fast"] = ind.ema(out["close"], cfg.ema_fast)
    out["ema_slow"] = ind.ema(out["close"], cfg.ema_slow)
    out["atr"] = ind.atr(out, cfg.atr_period)

    out = pd.merge_asof(
        out, bias_df.sort_index(), left_index=True, right_index=True, direction="backward"
    )

    cross_up = (out["ema_fast"] > out["ema_slow"]) & (out["ema_fast"].shift(1) <= out["ema_slow"].shift(1))
    cross_down = (out["ema_fast"] < out["ema_slow"]) & (out["ema_fast"].shift(1) >= out["ema_slow"].shift(1))

    out["long_signal"] = cross_up & (out["htf_bias"] == "long")
    out["short_signal"] = cross_down & (out["htf_bias"] == "short")
    return out
