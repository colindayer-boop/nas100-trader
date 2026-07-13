---
type: strategy
key: S2
status: validated
venue: [MT5, Alpaca]
exit: bracket
validation: YES since 2026-07-12 (ported to daily-FVG lineage; hourly variant was inert)
stop_pct: 0.015
rr: 3.0
sharpe: 0.7
tags: [strategy, validated]
---
# S2 Gold FVG

London-session Fair Value Gap continuation on GLD/XAUUSD, long or short. Broker bracket exit -1.5% / 3:1.

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **FIXED**
- **What evidence supports it?** FIND_s2inert, `docs/STRATEGY_VALIDATION_AUDIT.md`
- **What killed alternatives?** none rejected against this strategy
- **What is shadowing / waiting?** not shadowed (live strategy)
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
