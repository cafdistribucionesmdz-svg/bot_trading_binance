import pandas as pd

from tradingbot.mtf_strategy import MTFStrategyConfig, generate_mtf_signals, htf_bias


def test_htf_bias_long_above_ma_short_below():
    prices = [100.0] * 60
    prices[-1] = 200.0  # ultimo cierre bien por encima de la media
    df = pd.DataFrame({"close": prices})
    bias = htf_bias(df, ma_period=50)
    assert bias.iloc[-1] == "long"


def test_no_long_signal_against_htf_bias():
    # tendencia menor sube (cruce alcista de EMA9/21) pero el sesgo HTF es bajista todo el tiempo
    idx_htf = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    htf_df = pd.DataFrame({"close": [100 - i * 0.1 for i in range(100)]}, index=idx_htf)

    idx_ltf = pd.date_range("2024-01-03", periods=60, freq="5min", tz="UTC")
    ltf_prices = [50 + i * 0.5 for i in range(60)]  # sube fuerte -> deberia cruzar EMA9 sobre EMA21
    ltf_df = pd.DataFrame(
        {
            "open": ltf_prices,
            "high": [p + 0.2 for p in ltf_prices],
            "low": [p - 0.2 for p in ltf_prices],
            "close": ltf_prices,
        },
        index=idx_ltf,
    )

    result = generate_mtf_signals(ltf_df, htf_df, MTFStrategyConfig())
    assert result["long_signal"].sum() == 0


def test_long_signal_when_htf_bias_agrees():
    idx_htf = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    htf_df = pd.DataFrame({"close": [100 + i * 0.5 for i in range(100)]}, index=idx_htf)  # sesgo alcista

    idx_ltf = pd.date_range("2024-01-03", periods=60, freq="5min", tz="UTC")
    ltf_prices = [50 + i * 0.5 for i in range(60)]
    ltf_df = pd.DataFrame(
        {
            "open": ltf_prices,
            "high": [p + 0.2 for p in ltf_prices],
            "low": [p - 0.2 for p in ltf_prices],
            "close": ltf_prices,
        },
        index=idx_ltf,
    )

    result = generate_mtf_signals(ltf_df, htf_df, MTFStrategyConfig())
    assert result["long_signal"].sum() >= 1
    assert result["short_signal"].sum() == 0
