---
type: strategy
key: S5
status: validated
venue: [MT5, Alpaca]
exit: bracket
validation: PARTIAL on CFD (9:00 bar is not an auction open on NAS100; measured via fills)
stop_pct: 0.01
rr: 3.0
sharpe: 1.0
tags: [strategy, validated]
---
# S5 ORB

Opening Range Breakout: enter on break of the 9:00 ET hourly bar, breakout window 10-13 ET, volume-confirmed, long in bull / short in 200d-bear. Broker bracket -1% / 3:1. **No GEX gate -> most frequent live trader** (~1.5 signals/day pre-filter). Canary: [[08-Incidents-and-Postmortems/_index|watchdog]] alerts if the 9:00 bar goes missing. Foundation: Zarattini/Aziz/Barbon ORB paper.

Back: [[03-Validated-Strategies/_index|Validated Strategies]] | [[04 Risk Engine]] | [[06 Execution Engine]]

<!-- KG-NAV:START -->
## Navigation (auto -- from knowledge graph)
- **Why does this exist?** validated lineage; current validation status **PARTIAL-CFD**
- **What evidence supports it?** `docs/S5_REENTRY_REVIEW.md`, `docs/STRATEGY_VALIDATION_AUDIT.md`, `docs/LIVE_RESEARCH_DRIFT.md`, `docs/WEEKEND_EXPOSURE_AUDIT.md`
- **What killed alternatives?** `research/experiments/atr_compression_review.py`
- **What is shadowing / waiting?** `docs/ETF_FORWARD_SHADOW_REVIEW.md`, `research/ideas/2026-07-11-vix-term-structure-regime-gate.md`
- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]

See also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page
<!-- KG-NAV:END -->
