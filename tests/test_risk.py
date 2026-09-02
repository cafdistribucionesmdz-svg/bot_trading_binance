from tradingbot.risk import cap_position_size, position_size


def test_position_size_respects_risk_amount():
    qty = position_size(capital=1000, entry_price=100, stop_price=98, risk_pct=0.01)
    # riesgo = 1000*0.01 = 10; distancia stop = 2 -> qty = 5
    assert abs(qty - 5.0) < 1e-9


def test_position_size_zero_when_no_stop_distance():
    qty = position_size(capital=1000, entry_price=100, stop_price=100, risk_pct=0.01)
    assert qty == 0.0


def test_cap_position_size_limits_notional():
    qty = cap_position_size(qty=100, entry_price=100, capital=1000, leverage=5)
    # notional maximo = 1000*5 = 5000 -> qty maximo = 50
    assert abs(qty - 50.0) < 1e-9


def test_cap_position_size_no_change_when_within_limit():
    qty = cap_position_size(qty=10, entry_price=100, capital=1000, leverage=5)
    assert qty == 10
