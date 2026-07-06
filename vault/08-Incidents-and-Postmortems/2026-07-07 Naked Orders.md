---
type: incident
date: 2026-07-07
severity: critical
status: resolved
tags: [incident, postmortem]
---
# Naked orders - no live SL/TP

**Impact:** live MT5 orders placed with NO stop-loss / take-profit. Two NAS100 buys sat open unprotected (one at -136).\n\n**Root cause:** backtest SIMULATES exits in a loop; the live MT5 adapter placed the entry but never forwarded the stop/target to the broker. Exit logic existed for Alpaca, never for MT5. `place_order_safe` had no sl/tp params.\n\n**Fix:** thread `sl/tp` price levels through `place_order_safe` -> MT5 attaches broker-side brackets atomically. S1/S2/S4/S5/SWEEP pass both; S3 SL-only; BTC bracket + reconcile; OVN 5% catastrophe stop. `protect_positions.py` retrofits open positions.\n\n**Lesson:** the broker enforces the stop, not the bot. Verify a live order CARRIES its stop. See [[LIVE_SAFETY_AUDIT]].

Back: [[08-Incidents-and-Postmortems/_index|Incidents]]
