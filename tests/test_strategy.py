import pandas as pd

from tradingbot.strategy import StrategyConfig, generate_signals, signals_from_indicators


def test_long_signal_fires_on_rsi_cross_up_during_uptrend():
    data = pd.DataFrame(
        {
            "ema_fast": [10, 10, 10],
            "ema_slow": [9, 9, 9],
            "rsi": [45, 55, 60],
        }
    )
    result = signals_from_indicators(data, StrategyConfig())
    assert result["long_signal"].tolist() == [False, True, False]
    assert result["short_signal"].tolist() == [False, False, False]


def test_short_signal_fires_on_rsi_cross_down_during_downtrend():
    data = pd.DataFrame(
        {
            "ema_fast": [9, 9, 9],
            "ema_slow": [10, 10, 10],
            "rsi": [55, 45, 40],
        }
    )
    result = signals_from_indicators(data, StrategyConfig())
    assert result["short_signal"].tolist() == [False, True, False]
    assert result["long_signal"].tolist() == [False, False, False]


def test_no_long_signal_if_rsi_crosses_up_against_the_trend():
    # RSI cruza sobre 50 pero la tendencia es bajista -> no debe habilitar un long
    data = pd.DataFrame(
        {
            "ema_fast": [9, 9, 9],
            "ema_slow": [10, 10, 10],
            "rsi": [45, 55, 60],
        }
    )
    result = signals_from_indicators(data, StrategyConfig())
    assert result["long_signal"].sum() == 0
    assert result["short_signal"].sum() == 0


def test_generate_signals_computes_expected_columns_from_prices():
    prices = [100 + i * 0.5 for i in range(60)]
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.2 for p in prices],
            "low": [p - 0.2 for p in prices],
            "close": prices,
        }
    )
    result = generate_signals(df, StrategyConfig())
    for col in ["ema_fast", "ema_slow", "rsi", "atr", "long_signal", "short_signal"]:
        assert col in result.columns
    assert len(result) == len(df)
