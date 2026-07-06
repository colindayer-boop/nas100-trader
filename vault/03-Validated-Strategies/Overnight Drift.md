---
type: strategy
key: OVN
status: validated
venue: [MT5, Alpaca]
exit: time
stop_pct: 0.05
rr: null
sharpe: 0.68
tags: [strategy, validated]
---
# Overnight Drift

Long QQQ/US100 into Tue+Wed mornings (enter 15:00-16:00 ET, exit 09:30-11:00 ET). **Exit: time (next open)** + a WIDE 5% catastrophe stop as a VPS-death net (never triggers in normal moves).

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]
