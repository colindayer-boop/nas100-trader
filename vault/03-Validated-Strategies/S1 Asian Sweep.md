---
type: strategy
key: S1
status: validated
venue: [MT5, Alpaca]
exit: bracket
stop_pct: 0.015
rr: 3.0
sharpe: 1.0
tags: [strategy, validated]
---
# S1 Asian Sweep

Long QQQ/US100 when price sweeps below the overnight (Asian-session) low then reclaims it, gated by NEGATIVE GEX and VIX regime. A liquidity/stop-run reversal.\n\n- **Exit:** broker bracket, stop -1.5%, target 3:1 RR.\n- **Gates:** negative GEX (dealers short gamma), VIX 21d not extreme.\n- **Frequency:** ~11/yr (sparse by design).\n- Bull filter REMOVED (validated: works in bear too, OOS 0.88->1.02).

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]
