---
type: broker
brackets: yes
status: production
use: CFD-prop
tags: [broker]
---
# MT5 / Pepperstone

The live prop path. login 61552095, Pepperstone-Demo (Hedge).\n\n- **Brackets:** SL+TP attached atomically in `TRADE_ACTION_DEAL` (rejected order != naked fill). Clamped to symbol min stop distance.\n- **Symbol map:** QQQ->US100, SPY->US500, GLD->XAUUSD, BTC->BTCUSD. `RESTRICTED_UNIVERSE=True` (US single stocks unavailable).\n- **Timezone:** server time (UTC+3) rebased to UTC->ET; verified 9:00 ET + Asian bars present.\n- Windows-only (`MetaTrader5` pkg); runs on the VPS. See [[07 Deployment]].

Back: [[05-Broker-Integrations/_index|Broker Integrations]]
