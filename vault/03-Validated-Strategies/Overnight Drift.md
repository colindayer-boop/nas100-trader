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

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **YES**
- **What evidence supports it?** `docs/OVERNIGHT_MOMENTUM_REVIEW.md`
- **What killed alternatives?** none rejected against this strategy
- **What is shadowing / waiting?** not shadowed (live strategy)
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
