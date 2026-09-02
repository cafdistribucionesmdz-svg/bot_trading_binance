"""Estrategia de price action con estructura de mercado.

Replica FIEL (linea a linea) de la logica del bot real que corre en MT5:
detectar_swings / determinar_tendencia / es_pin_bar_* / es_envolvente_* /
buscar_senal_entrada / el calculo de SL-TP-R de enviar_orden / y el ratchet
de trailing de actualizar_trailing_stops.

Diferencias respecto a una simulacion tick-a-tick (inevitables al trabajar
con velas OHLC en vez de al bot viviendo con precios en tiempo real):

- Entrada: el bot real entra al precio de mercado (tick) apenas confirma la
  señal en la ultima vela cerrada. Ac​a se aproxima entrando en la apertura
  de la vela siguiente a la señal (no hay forma de sabre el tick exacto).
- Estructura: el bot real recalcula los swings cada ciclo sobre las ultimas
  (STRUCTURE_LOOKBACK + FETCH_BUFFER) velas (ventana deslizante). Ac​a se
  reproduce filtrando, en cada vela, los swings confirmados cuyo indice cae
  dentro de esa misma ventana reciente.
- Trailing: el bot real chequea el precio cada 1 minuto (~continuo). Ac​a
  el progreso de trailing solo se detecta a resolucion de vela (M15), lo
  cual es una aproximacion mas conservadora (menos oportunidades de
  "amarrar" un escalon de trailing dentro de una misma vela).
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .backtester import BacktestConfig, Trade
from .risk import cap_position_size, position_size


@dataclass
class PriceActionConfig:
    swing_lookback: int = 5  # SWING_LOOKBACK
    structure_lookback: int = 50  # STRUCTURE_LOOKBACK
    fetch_buffer: int = 10  # el "+10" que se pide de mas al bajar velas
    pullback_tolerance_pct: float = 0.0015  # 0.15%, igual que el bot real
    pin_bar_wick_body_mult: float = 2.0  # mecha >= 2x cuerpo
    pin_bar_body_ratio: float = 0.35  # cuerpo <= 35% del rango total
    sl_buffer_price: float = 0.0010  # margen fijo de precio (10 pips en EURUSD/GBPUSD)
    initial_tp_r: float = 2.0  # RISK_REWARD_INICIAL
    trailing_step_r: float = 1.0  # TRAILING_STEP_R
    rr_maximo: float = 4.0  # RR_MAXIMO

    @property
    def structure_window(self) -> int:
        return self.structure_lookback + self.fetch_buffer


def _es_pin_bar_alcista(o: float, h: float, l: float, c: float, cfg: PriceActionConfig) -> bool:
    cuerpo = abs(c - o)
    rango_total = h - l
    if rango_total == 0:
        return False
    mecha_inferior = min(o, c) - l
    return (mecha_inferior >= cfg.pin_bar_wick_body_mult * cuerpo) and (cuerpo <= cfg.pin_bar_body_ratio * rango_total)


def _es_pin_bar_bajista(o: float, h: float, l: float, c: float, cfg: PriceActionConfig) -> bool:
    cuerpo = abs(c - o)
    rango_total = h - l
    if rango_total == 0:
        return False
    mecha_superior = h - max(o, c)
    return (mecha_superior >= cfg.pin_bar_wick_body_mult * cuerpo) and (cuerpo <= cfg.pin_bar_body_ratio * rango_total)


def compute_confirmations(df: pd.DataFrame, cfg: PriceActionConfig) -> pd.DataFrame:
    out = df.copy()

    k = cfg.swing_lookback
    window = 2 * k + 1
    out["is_swing_high"] = out["high"] == out["high"].rolling(window, center=True).max()
    out["is_swing_low"] = out["low"] == out["low"].rolling(window, center=True).min()

    o, h, l, c = out["open"], out["high"], out["low"], out["close"]
    prev_o, prev_c = o.shift(1), c.shift(1)

    bullish_pin = [
        _es_pin_bar_alcista(oi, hi, li, ci, cfg) for oi, hi, li, ci in zip(o, h, l, c)
    ]
    bearish_pin = [
        _es_pin_bar_bajista(oi, hi, li, ci, cfg) for oi, hi, li, ci in zip(o, h, l, c)
    ]
    out["bullish_pin"] = bullish_pin
    out["bearish_pin"] = bearish_pin

    prev_bearish = prev_c < prev_o
    prev_bullish = prev_c > prev_o
    cur_bullish = c > o
    cur_bearish = c < o
    bullish_engulf = prev_bearish & cur_bullish & (o <= prev_c) & (c >= prev_o)
    bearish_engulf = prev_bullish & cur_bearish & (o >= prev_c) & (c <= prev_o)

    out["bullish_confirmation"] = (out["bullish_pin"] | bullish_engulf.fillna(False))
    out["bearish_confirmation"] = (out["bearish_pin"] | bearish_engulf.fillna(False))
    return out


def run_backtest(df: pd.DataFrame, cfg: PriceActionConfig, bt_cfg: BacktestConfig):
    data = compute_confirmations(df, cfg)
    n = len(data)

    highs = data["high"].to_numpy()
    lows = data["low"].to_numpy()
    opens = data["open"].to_numpy()
    is_sw_high = data["is_swing_high"].to_numpy()
    is_sw_low = data["is_swing_low"].to_numpy()
    bull_conf = data["bullish_confirmation"].to_numpy()
    bear_conf = data["bearish_confirmation"].to_numpy()
    index = data.index

    k = cfg.swing_lookback
    window = cfg.structure_window

    swing_highs: list[tuple[int, float]] = []  # (indice, precio), en orden cronologico
    swing_lows: list[tuple[int, float]] = []

    capital = bt_cfg.initial_capital
    equity_curve = []
    trades: list[Trade] = []

    position = None  # dict: trade, r, sl_r, tp_r
    pending_entry = None  # (side, sl) confirmado en la vela anterior

    for i in range(n):
        j = i - k
        if j >= 0:
            if is_sw_high[j]:
                swing_highs.append((j, highs[j]))
            if is_sw_low[j]:
                swing_lows.append((j, lows[j]))

        # ventana deslizante: se descartan swings que quedaron fuera de las
        # ultimas `structure_window` velas (como el bot real, que solo baja
        # las ultimas STRUCTURE_LOOKBACK+FETCH_BUFFER velas cada ciclo)
        cutoff = i - window
        while swing_highs and swing_highs[0][0] <= cutoff:
            swing_highs.pop(0)
        while swing_lows and swing_lows[0][0] <= cutoff:
            swing_lows.pop(0)

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
                        "sl_r": -1.0,
                        "tp_r": cfg.initial_tp_r,
                    }
        pending_entry = None

        if position is not None:
            trade: Trade = position["trade"]
            r = position["r"]

            favorable_r = (highs[i] - trade.entry_price) / r if trade.side == "long" else (
                trade.entry_price - lows[i]
            ) / r

            # ratchet de trailing: identico al while() de actualizar_trailing_stops()
            tp_r = position["tp_r"]
            sl_r = position["sl_r"]
            changed = False
            while favorable_r >= tp_r and tp_r < cfg.rr_maximo - 1e-9:
                sl_r = tp_r - cfg.initial_tp_r
                tp_r = min(cfg.rr_maximo, tp_r + cfg.trailing_step_r)
                changed = True
            if changed:
                position["sl_r"] = sl_r
                position["tp_r"] = tp_r
                if trade.side == "long":
                    trade.sl = trade.entry_price + sl_r * r
                    trade.tp = trade.entry_price + tp_r * r
                else:
                    trade.sl = trade.entry_price - sl_r * r
                    trade.tp = trade.entry_price - tp_r * r

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

        if position is None and swing_highs and swing_lows:
            if len(swing_highs) >= 2 and len(swing_lows) >= 2:
                ultimo_high, penultimo_high = swing_highs[-1][1], swing_highs[-2][1]
                ultimo_low, penultimo_low = swing_lows[-1][1], swing_lows[-2][1]
                alcista = ultimo_high > penultimo_high and ultimo_low > penultimo_low
                bajista = ultimo_high < penultimo_high and ultimo_low < penultimo_low
            else:
                alcista = bajista = False

            if alcista:
                nivel_estructura = swing_lows[-1][1]
                cerca_del_soporte = lows[i] <= nivel_estructura * (1 + cfg.pullback_tolerance_pct)
                if cerca_del_soporte and bull_conf[i]:
                    sl = nivel_estructura - cfg.sl_buffer_price
                    pending_entry = ("long", sl)
            elif bajista:
                nivel_estructura = swing_highs[-1][1]
                cerca_de_resistencia = highs[i] >= nivel_estructura * (1 - cfg.pullback_tolerance_pct)
                if cerca_de_resistencia and bear_conf[i]:
                    sl = nivel_estructura + cfg.sl_buffer_price
                    pending_entry = ("short", sl)

        equity_curve.append((ts, capital))

    equity_df = pd.DataFrame(equity_curve, columns=["time", "equity"]).set_index("time")
    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    return trades_df, equity_df
