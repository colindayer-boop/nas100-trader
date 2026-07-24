# RUNBOOK — ORPHAN POSITION

An **orphan** = a broker position whose `(magic, comment)` has no entry in the immutable
`position_ledger`. Policy: **alert, block all new orders, never assume ownership, require human
classification.**

1. Detection: `position_ledger.classify_broker_positions(...)` returns `block_all_orders=True` with the
   orphan list. Automated systems must halt new entries immediately.
2. For each orphan, a human determines the source: magic number, comment, opening timestamp, and the
   MT5 Experts/Journal log around that time.
3. Classify as one of: **ours-but-unledgered** (a pre-rewire trade — e.g. the BTC/770001 positions),
   **third-party EA** (a marketplace EA still attached), or **manual**.
4. Only after classification: decide to leave, hedge, or close **manually** (never automatically).
5. Add a reconciliation note to the ledger (append-only). Do not back-date or edit history.
6. New orders stay blocked until zero orphans remain.

**Current known orphans:** the 3 BTCUSD longs (magic 770001) are *ours-but-unledgered* — placed by
`live_trader.py` before the rewire. They must be human-classified and the legacy path retired before
any restart.
