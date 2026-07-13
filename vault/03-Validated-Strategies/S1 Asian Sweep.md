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

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **YES**
- **What evidence supports it?** `docs/LIVE_TRADING_PARITY.md`, `docs/STRATEGY_VALIDATION_AUDIT.md`, `docs/WEEKEND_EXPOSURE_AUDIT.md`
- **What killed alternatives?** `research/archive/EXP-20260710-01-dix-regime-filter-on-3-pillars.md`
- **What is shadowing / waiting?** `docs/ETF_FORWARD_SHADOW_REVIEW.md`
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
