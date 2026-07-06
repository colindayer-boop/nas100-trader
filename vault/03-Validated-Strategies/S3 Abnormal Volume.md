---
type: strategy
key: S3
status: validated
venue: [Alpaca, MT5-partial]
exit: time
stop_pct: 0.02
rr: null
sharpe: 0.6
tags: [strategy, validated]
---
# S3 Abnormal Volume

Buy on an abnormal-volume up day (z>1.5), hold 5 days. **Exit: 5-day time hold**, protected by a broker stop -2%. On MT5 only QQQ/GLD resolve.

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]
