# Bot de Trading — Binance Futures (EMA 9/21 + RSI 14 + ATR)

Bot en Python para operar futuros de Binance (USDT-M), pensado para arrancar
siempre en **Testnet** antes de tocar dinero real.

## Estrategia

- **Timeframe:** velas de 3-5 minutos.
- **Filtro de tendencia:** EMA(9) vs EMA(21). EMA9 > EMA21 = tendencia alcista,
  EMA9 < EMA21 = tendencia bajista.
- **Disparador de entrada:** cruce del RSI(14) sobre/bajo el nivel 50, a favor
  de la tendencia vigente (long solo en tendencia alcista, short solo en
  tendencia bajista).
- **Salida:** Stop Loss = 1×ATR(14), Take Profit = 1.5×ATR(14), calculados en
  la vela donde se confirma la señal (se adaptan a la volatilidad del
  momento).
- **Riesgo por operación:** configurable, 0.5%-1% del capital (`RISK_PCT`).
  El tamaño de posición se calcula para que, si se toca el SL, la pérdida sea
  exactamente ese porcentaje del capital.

Los parámetros (períodos de EMA/RSI/ATR, multiplicadores, símbolo, riesgo,
apalancamiento) se ajustan en `.env`, ver `.env.example`.

## Estructura del proyecto

```
tradingbot/
  indicators.py      EMA, RSI, ATR
  strategy.py         Señales de entrada (tendencia + disparador RSI)
  risk.py               Tamaño de posición según % de riesgo
  backtester.py       Motor de backtest sobre velas históricas
  data.py               Descarga de velas históricas (datos públicos)
  exchange_client.py  Cliente de Binance Futures (ccxt), con Testnet
  live_trader.py        Loop de trading en vivo/testnet
  config.py             Configuración desde variables de entorno
scripts/
  download_data.py     Descarga histórico a CSV
  run_backtest.py       Corre el backtest sobre un CSV
  run_live_testnet.py  Arranca el bot en vivo (testnet por defecto)
tests/                  Tests unitarios (pytest)
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## 1) Backtest (sin conectar ninguna cuenta)

Los datos históricos de velas son públicos, no hace falta API key para
descargarlos:

```bash
python scripts/download_data.py --symbol BTC/USDT --timeframe 5m --days 90
python scripts/run_backtest.py --data data/BTCUSDT_5m.csv --capital 1000 --risk-pct 0.01 --leverage 5
```

Esto imprime métricas (trades, win rate, profit factor, retorno total, máximo
drawdown) y guarda el detalle de cada operación en un CSV junto a los datos.

Ajustá los parámetros de la estrategia en `tradingbot/strategy.py`
(`StrategyConfig`) o vía las variables `EMA_FAST`, `EMA_SLOW`, `RSI_PERIOD`,
`RSI_TRIGGER`, `ATR_PERIOD`, `ATR_SL_MULT`, `ATR_TP_MULT` del `.env` para el
modo live.

## 2) Testnet de Binance Futures

1. Creá una cuenta de prueba en https://testnet.binancefuture.com
2. Generá tu API Key / Secret de testnet (fondos ficticios).
3. Completá `.env`:
   ```
   BINANCE_API_KEY=...
   BINANCE_API_SECRET=...
   BINANCE_TESTNET=true
   SYMBOL=BTC/USDT
   TIMEFRAME=5m
   ```
4. Arrancá el bot:
   ```bash
   python scripts/run_live_testnet.py
   ```

El bot sondea las velas cerradas del símbolo/timeframe configurado, calcula
las señales y, si no hay posición abierta y aparece una señal, entra a
mercado con órdenes de Stop Loss y Take Profit (`STOP_MARKET` /
`TAKE_PROFIT_MARKET`) ya cargadas. Revisá la ejecución en el panel de
Binance Testnet para confirmar que todo se comporta como esperás antes de
pensar en pasar a producción.

## 3) Cuenta real

Recién cuando el backtest y varios días/semanas en Testnet den resultados
consistentes, considerá pasar a producción: `BINANCE_TESTNET=false` y claves
reales con permisos de Futuros. El script pide una confirmación explícita
(`CONFIRMO`) antes de operar con dinero real. Aun así, no hay garantía de
resultados: el trading algorítmico puede perder dinero, incluso con una
estrategia bien testeada.

## Tests

```bash
pytest
```

## Advertencia

Este bot es una herramienta educativa/de investigación. No es asesoramiento
financiero. Probá siempre en Testnet, empezá con capital que puedas perder,
y monitoreá el bot activamente — ninguna estrategia automatizada está exenta
de riesgo (bugs, cortes de conexión, gaps de mercado, liquidaciones por
apalancamiento, etc.).
