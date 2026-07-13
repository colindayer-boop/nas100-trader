---
type: strategy
key: BTCT
status: validated
venue: [MT5]
exit: state-machine
stop_pct: n/a
rr: null
sharpe: 0.67
tags: [strategy, validated]
---
# BTC Trend

Vol-targeted Donchian 20/10 trend on BTC, rebalanced to target vol each run (state-machine). **Yellow risk**: no broker stop (rebalance-managed) - keep on demo until funded. See [[LIVE_SAFETY_AUDIT]].

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **YES**
- **What evidence supports it?** see audits
- **What killed alternatives?** `research/ideas/2026-07-12-intraday-return-momentum-decomposition.md`
- **What is shadowing / waiting?** not shadowed (live strategy)
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
