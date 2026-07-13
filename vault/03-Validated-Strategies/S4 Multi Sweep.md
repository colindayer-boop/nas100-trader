---
type: strategy
key: S4
status: validated
venue: [MT5, Alpaca]
exit: bracket
stop_pct: 0.015
rr: 3.0
sharpe: 0.9
tags: [strategy, validated]
---
# S4 Multi Sweep

Asian-sweep across QQQ + SPY, negative-GEX gated. Broker bracket -1.5% / 3:1.

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **YES**; depends on S1
- **What evidence supports it?** `docs/LIVE_TRADING_PARITY.md`, `docs/STRATEGY_VALIDATION_AUDIT.md`
- **What killed alternatives?** none rejected against this strategy
- **What is shadowing / waiting?** not shadowed (live strategy)
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
