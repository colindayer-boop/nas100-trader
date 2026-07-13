---
type: strategy
key: S3
status: validated
venue: [Alpaca, MT5-partial]
exit: time
validation: PARTIAL (live rule = strict subset ~4/yr vs validated 15/yr -- post-window decision)
stop_pct: 0.02
rr: null
sharpe: 0.6
tags: [strategy, validated]
---
# S3 Abnormal Volume

Buy on an abnormal-volume up day (z>1.5), hold 5 days. **Exit: 5-day time hold**, protected by a broker stop -2%. On MT5 only QQQ/GLD resolve.

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **PARTIAL**
- **What evidence supports it?** `docs/STRATEGY_VALIDATION_AUDIT.md`, `docs/S3_VALIDATION_REVIEW.md`, `docs/WEEKEND_EXPOSURE_AUDIT.md`
- **What killed alternatives?** FIND_weekend
- **What is shadowing / waiting?** not shadowed (live strategy)
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
