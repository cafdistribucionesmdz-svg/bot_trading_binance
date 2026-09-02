"""Gestion de riesgo: tamano de posicion segun % de capital arriesgado y distancia al SL."""


def position_size(capital: float, entry_price: float, stop_price: float, risk_pct: float) -> float:
    """Cantidad (en el activo base) tal que si se toca el stop se pierde `risk_pct` del capital."""
    risk_amount = capital * risk_pct
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        return 0.0
    return risk_amount / stop_distance


def cap_position_size(qty: float, entry_price: float, capital: float, leverage: int) -> float:
    """Recorta la cantidad para no superar el notional maximo permitido por el apalancamiento."""
    if qty <= 0:
        return 0.0
    max_notional = capital * leverage
    notional = qty * entry_price
    if notional > max_notional:
        return max_notional / entry_price
    return qty
