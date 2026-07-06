---
type: strategy
key: BTC
status: validated
venue: [MT5]
exit: bracket + state-machine
stop_pct: 0.025
rr: 3.0
sharpe: 0.67
tags: [strategy, validated]
---
# BTC Sweep

BTC Asian-sweep (00-08 UTC range, reclaim 08-16 UTC, EMA50>EMA200 uptrend). **Broker bracket -2.5% / 3:1 + state-machine reconcile** (if broker closes it, clear state, never re-sell -> no accidental short). Runs on MT5/BTCUSD (Binance geo-blocked on cloud).

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]
