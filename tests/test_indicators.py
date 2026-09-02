import pandas as pd

from tradingbot.indicators import atr, ema, rsi


def test_ema_converges_to_constant_price():
    s = pd.Series([100.0] * 50)
    result = ema(s, 9)
    assert abs(result.iloc[-1] - 100.0) < 1e-6


def test_rsi_all_gains_is_100():
    s = pd.Series(range(1, 30))
    result = rsi(s, 14)
    assert result.iloc[-1] > 99


def test_rsi_all_losses_is_0():
    s = pd.Series(range(30, 1, -1))
    result = rsi(s, 14)
    assert result.iloc[-1] < 1


def test_atr_zero_when_flat():
    df = pd.DataFrame(
        {
            "high": [100.0] * 20,
            "low": [100.0] * 20,
            "close": [100.0] * 20,
        }
    )
    result = atr(df, 14)
    assert result.iloc[-1] == 0
