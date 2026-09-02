"""Configuracion centralizada, cargada desde variables de entorno / .env."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    testnet: bool = field(default_factory=lambda: _env_bool("BINANCE_TESTNET", "true"))

    symbol: str = field(default_factory=lambda: os.getenv("SYMBOL", "BTC/USDT"))
    timeframe: str = field(default_factory=lambda: os.getenv("TIMEFRAME", "5m"))
    leverage: int = field(default_factory=lambda: int(os.getenv("LEVERAGE", "5")))
    risk_pct: float = field(default_factory=lambda: float(os.getenv("RISK_PCT", "0.01")))

    ema_fast: int = field(default_factory=lambda: int(os.getenv("EMA_FAST", "9")))
    ema_slow: int = field(default_factory=lambda: int(os.getenv("EMA_SLOW", "21")))
    rsi_period: int = field(default_factory=lambda: int(os.getenv("RSI_PERIOD", "14")))
    rsi_trigger: float = field(default_factory=lambda: float(os.getenv("RSI_TRIGGER", "50")))
    atr_period: int = field(default_factory=lambda: int(os.getenv("ATR_PERIOD", "14")))
    atr_sl_mult: float = field(default_factory=lambda: float(os.getenv("ATR_SL_MULT", "1.0")))
    atr_tp_mult: float = field(default_factory=lambda: float(os.getenv("ATR_TP_MULT", "1.5")))
