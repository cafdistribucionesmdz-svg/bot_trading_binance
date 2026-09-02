import pandas as pd

from tradingbot.backtester import BacktestConfig
from tradingbot.price_action_strategy import PriceActionConfig, compute_confirmations, run_backtest


def _bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


# Estructura limpia: Peak1(idx4) -> Trough1(idx8) -> Peak2(idx14, mas alto) ->
# Trough2(idx17, mas alto) -> pullback que confirma con una vela de reversion (idx20/21).
_BASE_BARS = [
    _bar(100.00, 100.20, 99.90, 100.10),
    _bar(100.10, 100.40, 100.00, 100.30),
    _bar(100.30, 100.60, 100.20, 100.50),
    _bar(100.50, 100.90, 100.40, 100.80),
    _bar(100.80, 101.20, 100.70, 101.00),  # idx4: Peak1
    _bar(101.00, 101.05, 100.60, 100.70),
    _bar(100.70, 100.80, 100.20, 100.30),
    _bar(100.30, 100.40, 99.80, 99.90),
    _bar(99.90, 100.00, 99.50, 99.70),  # idx8: Trough1
    _bar(99.70, 100.20, 99.60, 100.10),
    _bar(100.10, 100.80, 100.00, 100.70),
    _bar(100.70, 101.50, 100.60, 101.40),
    _bar(101.40, 102.30, 101.30, 102.20),
    _bar(102.20, 103.10, 102.10, 103.00),
    _bar(103.00, 103.60, 102.90, 103.50),  # idx14: Peak2 (mas alto que Peak1)
    _bar(103.50, 103.55, 102.90, 103.00),
    _bar(103.00, 103.10, 102.30, 102.40),
    _bar(102.40, 102.50, 101.80, 101.90),  # idx17: Trough2 (mas alto que Trough1)
    _bar(101.90, 102.45, 101.85, 102.00),
    _bar(102.00, 102.40, 101.90, 101.95),
    _bar(101.95, 102.35, 101.92, 102.00),
    _bar(102.15, 102.30, 101.85, 102.20),  # idx21: confirmacion (envolvente alcista), cerca del soporte
]

_DEFAULT_CFG = PriceActionConfig(swing_lookback=2, structure_lookback=50, fetch_buffer=10)
_BT_CFG = BacktestConfig(initial_capital=1000, risk_pct=0.01, leverage=10, taker_fee=0.0)


def test_bullish_pin_bar_is_detected():
    df = pd.DataFrame(
        [
            _bar(100, 100.2, 99.8, 100.1),
            _bar(100.1, 100.3, 98.0, 100.2),  # mecha inferior larga, cuerpo chico
        ]
    )
    out = compute_confirmations(df, PriceActionConfig())
    assert bool(out["bullish_pin"].iloc[1]) is True
    assert bool(out["bearish_pin"].iloc[1]) is False


def test_bullish_engulfing_is_detected():
    df = pd.DataFrame(
        [
            _bar(100, 100.1, 98.5, 98.6),  # vela bajista
            _bar(98.5, 101.0, 98.4, 100.8),  # vela alcista que engulle a la anterior
        ]
    )
    out = compute_confirmations(df, PriceActionConfig())
    assert bool(out["bullish_confirmation"].iloc[1]) is True


def test_long_trade_progresses_through_stages_to_4r_tp():
    bars = _BASE_BARS + [
        _bar(102.20, 102.30, 102.10, 102.25),  # entrada en la apertura
        _bar(102.25, 103.10, 102.20, 103.00),  # cruza +2R -> extiende a 3R, no cierra
        _bar(103.00, 103.50, 102.95, 103.40),  # cruza +3R -> asegura +1R, extiende a 4R
        _bar(103.40, 103.90, 103.35, 103.85),  # toca el TP final de 4R
    ]
    df = pd.DataFrame(bars)

    trades_df, _ = run_backtest(df, _DEFAULT_CFG, _BT_CFG)

    assert len(trades_df) == 1
    trade = trades_df.iloc[0]
    assert trade["side"] == "long"
    assert trade["exit_reason"] == "TP"
    assert trade["pnl"] == 40.0  # 4R sobre 1% de riesgo de 1000 = 10 -> 4*10


def test_trade_never_closes_in_loss_once_past_breakeven():
    bars = _BASE_BARS + [
        _bar(102.20, 102.30, 102.10, 102.25),  # entrada
        _bar(102.25, 103.10, 102.20, 103.00),  # cruza +2R -> SL a breakeven
        _bar(103.00, 103.05, 101.90, 102.00),  # se da vuelta y perfora breakeven
    ]
    df = pd.DataFrame(bars)

    trades_df, _ = run_backtest(df, _DEFAULT_CFG, _BT_CFG)

    assert len(trades_df) == 1
    trade = trades_df.iloc[0]
    assert trade["exit_reason"] == "SL"
    assert trade["pnl"] >= 0.0
    assert trade["exit_price"] == trade["entry_price"]


def test_structure_window_forgets_old_swings():
    """Con la ventana grande (default) la estructura completa esta disponible y
    entra el trade. Con una ventana chica, el primer swing (Peak1/Trough1) queda
    fuera de la ventana reciente antes de que se complete la estructura, por lo
    que nunca hay 2 swings validos y la señal no se dispara — a diferencia de
    una implementacion con memoria global de swings, que es justamente la
    diferencia clave con el bot real (que solo mira las ultimas N velas)."""
    bars = _BASE_BARS + [
        _bar(102.20, 102.30, 102.10, 102.25),
        _bar(102.25, 103.10, 102.20, 103.00),
        _bar(103.00, 103.50, 102.95, 103.40),
        _bar(103.40, 103.90, 103.35, 103.85),
    ]
    df = pd.DataFrame(bars)

    trades_wide, _ = run_backtest(df, _DEFAULT_CFG, _BT_CFG)
    assert len(trades_wide) == 1

    narrow_cfg = PriceActionConfig(swing_lookback=2, structure_lookback=8, fetch_buffer=2)
    trades_narrow, _ = run_backtest(df, narrow_cfg, _BT_CFG)
    assert len(trades_narrow) == 0


def test_no_trade_without_two_confirmed_swings_each_side():
    # Solo hay un tramo de suba, ningun swing high/low se repite -> sin estructura, sin señal
    prices = [100 + i * 0.3 for i in range(20)]
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "close": prices,
        }
    )
    trades_df, _ = run_backtest(df, _DEFAULT_CFG, _BT_CFG)
    assert len(trades_df) == 0
