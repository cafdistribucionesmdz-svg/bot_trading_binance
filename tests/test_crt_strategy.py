import pandas as pd

from tradingbot.crt_strategy import CRTConfig, generate_crt_signals


def _htf_df():
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [110.0, 110.0, 110.0],
            "low": [90.0, 90.0, 90.0],
            "close": [100.0, 100.0, 100.0],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="1D", tz="UTC"),
    )


def _flat_ltf_df():
    idx = pd.date_range("2024-01-02", periods=24, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0] * 24,
            "high": [101.0] * 24,
            "low": [99.0] * 24,
            "close": [100.0] * 24,
        },
        index=idx,
    )


def test_long_signal_on_sweep_of_low_then_reversal_inside_range():
    ltf_df = _flat_ltf_df()
    ltf_df.loc[ltf_df.index[10], ["low", "close"]] = [85.0, 88.0]  # barre el minimo, no revierte todavia
    ltf_df.loc[ltf_df.index[11], ["low", "high", "close"]] = [87.0, 93.0, 93.0]  # vuelve dentro del rango

    cfg = CRTConfig(atr_period=5)
    result = generate_crt_signals(ltf_df, _htf_df(), cfg)

    assert result["long_signal"].sum() == 1
    assert result["short_signal"].sum() == 0

    signal_row = result[result["long_signal"]].iloc[0]
    assert signal_row["tp_level"] == 110.0
    assert signal_row["sl_level"] < 85.0  # mas alla del extremo de la barrida


def test_short_signal_on_sweep_of_high_then_reversal_inside_range():
    ltf_df = _flat_ltf_df()
    ltf_df.loc[ltf_df.index[10], ["high", "close"]] = [115.0, 112.0]  # barre el maximo, no revierte todavia
    ltf_df.loc[ltf_df.index[11], ["high", "low", "close"]] = [113.0, 107.0, 107.0]  # vuelve dentro del rango

    cfg = CRTConfig(atr_period=5)
    result = generate_crt_signals(ltf_df, _htf_df(), cfg)

    assert result["short_signal"].sum() == 1
    assert result["long_signal"].sum() == 0

    signal_row = result[result["short_signal"]].iloc[0]
    assert signal_row["tp_level"] == 90.0
    assert signal_row["sl_level"] > 115.0


def test_only_one_signal_per_range_per_direction():
    ltf_df = _flat_ltf_df()
    ltf_df.loc[ltf_df.index[5], ["low", "close"]] = [85.0, 88.0]
    ltf_df.loc[ltf_df.index[6], ["low", "high", "close"]] = [87.0, 93.0, 93.0]
    # una segunda barrida+reversion el mismo dia no deberia generar una señal nueva
    ltf_df.loc[ltf_df.index[15], ["low", "close"]] = [86.0, 89.0]
    ltf_df.loc[ltf_df.index[16], ["low", "high", "close"]] = [88.0, 94.0, 94.0]

    cfg = CRTConfig(atr_period=5)
    result = generate_crt_signals(ltf_df, _htf_df(), cfg)
    assert result["long_signal"].sum() == 1


def test_no_signal_without_a_sweep():
    ltf_df = _flat_ltf_df()  # nunca sale del rango 90-110
    cfg = CRTConfig(atr_period=5)
    result = generate_crt_signals(ltf_df, _htf_df(), cfg)
    assert result["long_signal"].sum() == 0
    assert result["short_signal"].sum() == 0
