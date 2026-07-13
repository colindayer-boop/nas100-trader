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

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **PARTIAL**; depends on S1
- **What evidence supports it?** `docs/STRATEGY_VALIDATION_AUDIT.md`
- **What killed alternatives?** none rejected against this strategy
- **What is shadowing / waiting?** not shadowed (live strategy)
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
