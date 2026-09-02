"""Arranca el bot en vivo contra Binance Futures (Testnet por defecto).

Toda la configuracion sale de variables de entorno / .env (ver .env.example).
Uso:
    python scripts/run_live_testnet.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tradingbot.config import Settings
from tradingbot.exchange_client import BinanceFuturesClient, ExchangeConfig
from tradingbot.live_trader import run_live
from tradingbot.strategy import StrategyConfig


def main():
    s = Settings()

    if not s.testnet:
        confirm = input(
            "ATENCION: BINANCE_TESTNET=false, vas a operar con dinero REAL.\n"
            "Escribi 'CONFIRMO' para continuar: "
        )
        if confirm.strip() != "CONFIRMO":
            print("Cancelado.")
            return

    if not s.api_key or not s.api_secret:
        print("Faltan BINANCE_API_KEY / BINANCE_API_SECRET (ver .env.example).")
        return

    exch_cfg = ExchangeConfig(
        api_key=s.api_key,
        api_secret=s.api_secret,
        testnet=s.testnet,
        symbol=s.symbol,
        leverage=s.leverage,
    )
    client = BinanceFuturesClient(exch_cfg)

    strat_cfg = StrategyConfig(
        ema_fast=s.ema_fast,
        ema_slow=s.ema_slow,
        rsi_period=s.rsi_period,
        rsi_trigger=s.rsi_trigger,
        atr_period=s.atr_period,
        atr_sl_mult=s.atr_sl_mult,
        atr_tp_mult=s.atr_tp_mult,
    )

    run_live(client, strat_cfg, s.timeframe, s.risk_pct)


if __name__ == "__main__":
    main()
