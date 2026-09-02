import pandas as pd

from tradingbot.backtester import BacktestConfig
from tradingbot.price_action_strategy import PriceActionConfig, compute_confirmations, run_backtest


def _bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


def _uptrend_structure_bars():
    """Construye: swing high (105.1) -> swing low (101.9) -> swing high mas alto (108.1)
    -> swing low mas alto (104.4), confirmados, y termina con una vela de pullback que
    es un pin bar alcista tocando el segundo swing low."""
    bars = []
    for o, c in [(100, 101), (101, 102), (102, 103), (103, 104), (104, 105), (105, 104.5)]:
        bars.append(_bar(o, max(o, c) + 0.1, min(o, c) - 0.1, c))
    for o, c in [(104.5, 103.5), (103.5, 102.8), (102.8, 102)]:
        bars.append(_bar(o, max(o, c) + 0.1, min(o, c) - 0.1, c))
    for o, c in [(102, 104), (104, 106), (106, 107.5), (107.5, 108)]:
        bars.append(_bar(o, max(o, c) + 0.1, min(o, c) - 0.1, c))
    for o, c in [(108, 107), (107, 105.5), (105.5, 104.5)]:
        bars.append(_bar(o, max(o, c) + 0.1, min(o, c) - 0.1, c))
    for o, c in [(104.5, 105), (105, 105.3)]:
        bars.append(_bar(o, max(o, c) + 0.1, min(o, c) - 0.1, c))
    bars.append(_bar(105.2, 105.4, 104.35, 105.3))  # pin bar alcista (indice 18)
    return bars


def test_bullish_pin_bar_is_detected():
    df = pd.DataFrame(
        [
            _bar(100, 100.2, 99.8, 100.1),
            _bar(100.1, 100.3, 98.0, 100.2),  # mecha inferior larga, cuerpo chico
        ]
    )
    cfg = PriceActionConfig(atr_period=1)
    out = compute_confirmations(df, cfg)
    assert bool(out["bullish_confirmation"].iloc[1]) is True
    assert bool(out["bearish_confirmation"].iloc[1]) is False


def test_bullish_engulfing_is_detected():
    df = pd.DataFrame(
        [
            _bar(100, 100.1, 98.5, 98.6),  # vela bajista
            _bar(98.5, 101.0, 98.4, 100.8),  # vela alcista que engulle a la anterior
        ]
    )
    cfg = PriceActionConfig(atr_period=1)
    out = compute_confirmations(df, cfg)
    assert bool(out["bullish_confirmation"].iloc[1]) is True


def test_long_trade_progresses_through_stages_to_4r_tp():
    bars = _uptrend_structure_bars()
    bars += [
        _bar(105.5, 106.0, 105.3, 105.8),  # entrada en la apertura
        _bar(105.8, 108.0, 105.7, 107.9),  # cruza +2R -> deberia extender a 3R, no cerrar
        _bar(107.9, 109.5, 107.8, 109.3),  # cruza +3R -> asegura +1R, extiende a 4R
        _bar(109.3, 110.5, 109.2, 110.4),  # toca el TP final de 4R
    ]
    df = pd.DataFrame(bars)
    cfg = PriceActionConfig(atr_period=3, swing_lookback=2, sl_buffer_atr_mult=0.1, pullback_tolerance_atr_mult=0.5)
    bt_cfg = BacktestConfig(initial_capital=1000, risk_pct=0.01, leverage=10, taker_fee=0.0)

    trades_df, _ = run_backtest(df, cfg, bt_cfg)

    assert len(trades_df) == 1
    trade = trades_df.iloc[0]
    assert trade["side"] == "long"
    assert trade["exit_reason"] == "TP"
    assert trade["pnl"] == 40.0  # 4R sobre 1% de riesgo de 1000 = 10 -> 4*10


def test_trade_never_closes_in_loss_once_past_breakeven():
    bars = _uptrend_structure_bars()
    bars += [
        _bar(105.5, 106.0, 105.3, 105.8),  # entrada
        _bar(105.8, 108.0, 105.7, 107.9),  # cruza +2R -> SL a breakeven
        _bar(107.9, 108.0, 105.0, 105.2),  # se da vuelta y perfora breakeven
    ]
    df = pd.DataFrame(bars)
    cfg = PriceActionConfig(atr_period=3, swing_lookback=2, sl_buffer_atr_mult=0.1, pullback_tolerance_atr_mult=0.5)
    bt_cfg = BacktestConfig(initial_capital=1000, risk_pct=0.01, leverage=10, taker_fee=0.0)

    trades_df, _ = run_backtest(df, cfg, bt_cfg)

    assert len(trades_df) == 1
    trade = trades_df.iloc[0]
    assert trade["exit_reason"] == "SL"
    assert trade["pnl"] >= 0.0
