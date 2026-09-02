"""Cliente de Binance USDT-M Futures (via ccxt), con soporte de Testnet."""

from dataclasses import dataclass
from typing import Optional

import ccxt


@dataclass
class ExchangeConfig:
    api_key: str
    api_secret: str
    testnet: bool = True
    symbol: str = "BTC/USDT"
    leverage: int = 5


class BinanceFuturesClient:
    def __init__(self, cfg: ExchangeConfig):
        self.cfg = cfg
        self.exchange = ccxt.binanceusdm(
            {
                "apiKey": cfg.api_key,
                "secret": cfg.api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if cfg.testnet:
            self.exchange.set_sandbox_mode(True)

        self.exchange.load_markets()
        try:
            self.exchange.set_leverage(cfg.leverage, cfg.symbol)
        except Exception as exc:  # el exchange puede rechazar si ya esta seteado, no es fatal
            print(f"Aviso: no se pudo fijar el leverage automaticamente ({exc})")

    def fetch_ohlcv(self, timeframe: str, limit: int = 200):
        return self.exchange.fetch_ohlcv(self.cfg.symbol, timeframe=timeframe, limit=limit)

    def fetch_balance_usdt(self) -> float:
        balance = self.exchange.fetch_balance()
        return float(balance.get("total", {}).get("USDT", 0.0))

    def fetch_open_position(self) -> Optional[dict]:
        positions = self.exchange.fetch_positions([self.cfg.symbol])
        for p in positions:
            if abs(float(p.get("contracts") or 0)) > 0:
                return p
        return None

    def open_market_position(self, side: str, qty: float, sl_price: float, tp_price: float):
        order_side = "buy" if side == "long" else "sell"
        close_side = "sell" if side == "long" else "buy"

        entry_order = self.exchange.create_order(self.cfg.symbol, "market", order_side, qty)
        sl_order = self.exchange.create_order(
            self.cfg.symbol,
            "STOP_MARKET",
            close_side,
            qty,
            None,
            {"stopPrice": sl_price, "reduceOnly": True},
        )
        tp_order = self.exchange.create_order(
            self.cfg.symbol,
            "TAKE_PROFIT_MARKET",
            close_side,
            qty,
            None,
            {"stopPrice": tp_price, "reduceOnly": True},
        )
        return entry_order, sl_order, tp_order

    def close_position(self, side: str, qty: float):
        close_side = "sell" if side == "long" else "buy"
        return self.exchange.create_order(
            self.cfg.symbol, "market", close_side, qty, None, {"reduceOnly": True}
        )

    def cancel_all_open_orders(self):
        self.exchange.cancel_all_orders(self.cfg.symbol)
