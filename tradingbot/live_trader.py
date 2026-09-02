"""Loop de trading en vivo (pensado para Testnet): sondea velas cerradas y opera señales."""

import time

import pandas as pd

from .exchange_client import BinanceFuturesClient
from .risk import cap_position_size, position_size
from .strategy import StrategyConfig, generate_signals


def _ohlcv_to_df(raw) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")


def run_live(
    client: BinanceFuturesClient,
    strat_cfg: StrategyConfig,
    timeframe: str,
    risk_pct: float,
    poll_seconds: int = 15,
):
    modo = "TESTNET" if client.cfg.testnet else "PRODUCCION (dinero real)"
    print(f"Arrancando bot en {modo} sobre {client.cfg.symbol} ({timeframe})")

    min_velas = max(strat_cfg.ema_slow, strat_cfg.rsi_period, strat_cfg.atr_period) + 2
    last_closed_ts = None

    while True:
        try:
            raw = client.fetch_ohlcv(timeframe, limit=200)
            df = _ohlcv_to_df(raw)
            closed = df.iloc[:-1]  # la ultima vela del array aun esta en curso

            if len(closed) < min_velas:
                time.sleep(poll_seconds)
                continue

            data = generate_signals(closed, strat_cfg)
            last = data.iloc[-1]

            if last.name == last_closed_ts:
                time.sleep(poll_seconds)
                continue
            last_closed_ts = last.name

            position = client.fetch_open_position()

            if position is None and (last["long_signal"] or last["short_signal"]):
                side = "long" if last["long_signal"] else "short"
                entry_price = df.iloc[-1]["open"]
                atr_val = last["atr"]

                if pd.isna(atr_val) or atr_val <= 0:
                    print("ATR invalido, se omite la señal")
                    time.sleep(poll_seconds)
                    continue

                if side == "long":
                    sl = entry_price - strat_cfg.atr_sl_mult * atr_val
                    tp = entry_price + strat_cfg.atr_tp_mult * atr_val
                else:
                    sl = entry_price + strat_cfg.atr_sl_mult * atr_val
                    tp = entry_price - strat_cfg.atr_tp_mult * atr_val

                capital = client.fetch_balance_usdt()
                qty = position_size(capital, entry_price, sl, risk_pct)
                qty = cap_position_size(qty, entry_price, capital, client.cfg.leverage)
                qty = float(client.exchange.amount_to_precision(client.cfg.symbol, qty))

                if qty > 0:
                    print(
                        f"Señal {side.upper()} -> entrada~{entry_price:.2f} "
                        f"SL={sl:.2f} TP={tp:.2f} qty={qty}"
                    )
                    client.open_market_position(side, qty, sl, tp)
                else:
                    print("Tamaño de posicion calculado = 0, se omite la entrada")
            elif position is not None:
                print(f"Posicion abierta: {position.get('side')} qty={position.get('contracts')}")
            else:
                print(f"Sin señal en la vela {last.name}")

        except Exception as exc:
            print(f"Error en el loop de trading: {exc}")

        time.sleep(poll_seconds)
