import pandas as pd

from tradingbot.mean_reversion_strategy import MeanReversionConfig, generate_signals


def test_long_signal_on_bounce_back_inside_lower_band():
    # precio estable, cae fuerte (perfora banda inferior + RSI bajo), y se recupera
    prices = [100.0] * 25
    prices += [95, 90, 85, 80]  # caida fuerte -> banda inferior + RSI sobreventa
    prices += [88]  # vuelve a meterse dentro de la banda -> señal de largo

    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
        }
    )
    result = generate_signals(df, MeanReversionConfig())
    assert result["long_signal"].sum() >= 1
    assert result["short_signal"].sum() == 0


def test_short_signal_on_bounce_back_inside_upper_band():
    prices = [100.0] * 25
    prices += [105, 110, 115, 120]  # suba fuerte -> banda superior + RSI sobrecompra
    prices += [112]  # vuelve a meterse dentro de la banda -> señal de corto

    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
        }
    )
    result = generate_signals(df, MeanReversionConfig())
    assert result["short_signal"].sum() >= 1
    assert result["long_signal"].sum() == 0


def test_no_signal_when_price_stays_flat():
    prices = [100.0] * 40
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "close": prices,
        }
    )
    result = generate_signals(df, MeanReversionConfig())
    assert result["long_signal"].sum() == 0
    assert result["short_signal"].sum() == 0
