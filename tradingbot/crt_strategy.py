"""Estrategia CRT (Candle Range Theory).

Una vela de un timeframe mayor (por defecto, la vela diaria) define un "rango"
(su maximo y minimo). Dentro del periodo siguiente, en un timeframe menor (por
defecto 1h), se busca:

1. Barrida ("manipulacion"): el precio perfora el minimo (o el maximo) de esa
   vela de rango -> caza de stops / trampa de liquidez.
2. Reversion ("distribucion"): el precio vuelve a cerrar dentro del rango,
   confirmando que la ruptura fue falsa. Ahi se entra, en contra de la barrida.

Salida:
- Take profit: el lado opuesto del rango de la vela mayor.
- Stop loss: un poco mas alla del extremo de la barrida (colchon = una fraccion
  del ATR del timeframe menor, para adaptarse a la volatilidad).

Solo se toma una señal por rango y por direccion (evita reentradas repetidas
sobre el mismo rango).
"""

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind


@dataclass
class CRTConfig:
    htf_rule: str = "1D"  # regla de resample de pandas para construir el rango mayor
    atr_period: int = 14
    sl_buffer_atr_mult: float = 0.25


def resample_htf(ltf_df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        ltf_df.resample(rule)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )


def generate_crt_signals(ltf_df: pd.DataFrame, htf_df: pd.DataFrame, cfg: CRTConfig) -> pd.DataFrame:
    out = ltf_df.copy().sort_index()
    out["atr"] = ind.atr(out, cfg.atr_period)

    # El rango de la vela HTF que cerro en el periodo [t, t+1) recien esta disponible
    # a partir de t+1 (para no meter look-ahead bias).
    period = htf_df.index.to_series().diff().median()
    htf_shifted = htf_df[["high", "low"]].copy()
    htf_shifted.index = htf_shifted.index + period
    htf_shifted = htf_shifted.rename(columns={"high": "range_high", "low": "range_low"})

    out = pd.merge_asof(
        out, htf_shifted.sort_index(), left_index=True, right_index=True, direction="backward"
    )

    n = len(out)
    long_signal = [False] * n
    short_signal = [False] * n
    sl_level = [float("nan")] * n
    tp_level = [float("nan")] * n

    prev_range_low = None
    swept_low = swept_high = False
    long_taken = short_taken = False
    sweep_low_extreme = sweep_high_extreme = None

    lows = out["low"].to_numpy()
    highs = out["high"].to_numpy()
    closes = out["close"].to_numpy()
    range_lows = out["range_low"].to_numpy()
    range_highs = out["range_high"].to_numpy()
    atrs = out["atr"].to_numpy()

    for i in range(n):
        rl, rh = range_lows[i], range_highs[i]
        if pd.isna(rl) or pd.isna(rh) or pd.isna(atrs[i]):
            continue

        if rl != prev_range_low:
            swept_low = swept_high = False
            long_taken = short_taken = False
            sweep_low_extreme = sweep_high_extreme = None
            prev_range_low = rl

        if lows[i] < rl:
            swept_low = True
            sweep_low_extreme = lows[i] if sweep_low_extreme is None else min(sweep_low_extreme, lows[i])
        if highs[i] > rh:
            swept_high = True
            sweep_high_extreme = highs[i] if sweep_high_extreme is None else max(sweep_high_extreme, highs[i])

        if swept_low and not long_taken and closes[i] > rl:
            long_signal[i] = True
            long_taken = True
            sl_level[i] = sweep_low_extreme - cfg.sl_buffer_atr_mult * atrs[i]
            tp_level[i] = rh

        if swept_high and not short_taken and closes[i] < rh:
            short_signal[i] = True
            short_taken = True
            sl_level[i] = sweep_high_extreme + cfg.sl_buffer_atr_mult * atrs[i]
            tp_level[i] = rl

    out["long_signal"] = long_signal
    out["short_signal"] = short_signal
    out["sl_level"] = sl_level
    out["tp_level"] = tp_level
    return out
