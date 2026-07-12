---
type: research-note
date: 2026-07-12
tags: [audit, validation]
---
# Strategy Validation Audit (2026-07-12)

Provenance audit of all 8 strategies -- origin, validated timeframe/data/assumptions,
and whether live preserves them. Full table: docs/STRATEGY_VALIDATION_AUDIT.md.

**Findings:** S2 timeframe drift (fixed -- ported to daily-FVG lineage), **S3 rule
drift** (live = strict subset, ~4/yr vs validated 15/yr -- post-window decision),
S5-on-CFD premise weakness (measured via fills), BTC venue swap (month-end check).

Meta-lesson: parity audits verify code matches itself; VALIDATION audits verify code
still matches its evidence. Re-run on every timeframe/venue/data port.

[[02-Strategy-Research/_index|Research]] | [[03-Validated-Strategies/_index|Strategies]] | [[00 Dashboard]]
