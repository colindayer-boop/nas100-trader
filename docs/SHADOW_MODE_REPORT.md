# SHADOW_MODE_REPORT — PHASE 601 Stage 11

Shadow framework (`execution_safety/shadow.py`) runs the **full** production pipeline
(authorize → reconcile → ledger) for every eligible signal and records the hypothetical broker
command, but **places no order**. Invariant, test-proven: `placed_order is False` even on
`ALLOW_PAPER`.

## Demonstration: GSR "in the boot" (shadow)
The replicated Gold/Silver-Ratio strategy (`gsr_strategy.py`, real edge, TR-a921975d8eef2571) was run
through the boot in shadow:
```
GSR emitted: LONG silver @ 35.69  SL 32.12   (gsr-2025-06-05)
gate decision: BLOCK   reasons: ['NOT_PAPER_APPROVED']   placed_order: False
```
A genuine, validated edge generated a real signal and was **still blocked from trading** because its
contract status is `NEEDS_REPLICATION`, not `PAPER_APPROVED`. This is the fail-closed guarantee working
on a *good* strategy, not just a bad one.

## Soak status
The 30-day / ≥100-signal / multi-volatility soak has **NOT** been run (it requires live market time on
the VPS). The framework is built and unit-tested; the soak itself is pending and is a precondition for
any PAPER promotion (Stage 12).
