# SYSTEM_READINESS_REPORT — PHASE 601

Recovery objective: make unsupported trading technically impossible; fail closed. **No orders were
placed or closed by this work; MT5 AutoTrading was not enabled.** This is the mandated stop point.

## (1) What is PROVEN (automated tests, this repo)
Fail-closed gate — `execution_safety/test_fail_closed.py` **14/14** and `test_recovery.py` **7/7**:
- A signal **cannot call a broker** (structural test on `gate.py`).
- Trading is blocked when **any** of these is missing/invalid: strategy contract, PAPER_APPROVED
  status, frozen-version match, approved trial, permitted symbol, broker-side stop, deterministic
  volume, inference ALLOW, Guardian approval.
- An **implausible stop distance (>15%)** is rejected — the exact 20% BTC stop is blocked.
- **Guardian veto cannot be overridden**; a strong entry belief cannot average away a failed gate.
- **Demo/real guard:** PAPER_APPROVED may trade demo only; real needs LIVE_APPROVED.
- **Missing broker-side stop** after fill ⇒ CRITICAL ⇒ block new entries (reconciliation).
- **Orphan position** (unledgered broker position) ⇒ block all orders.
- **Prop survival:** a trade that could breach a firm's daily/total limit is rejected.
- **Shadow never places**, even on ALLOW_PAPER.
- **Parity:** all **3/3** real BTC trades are BLOCKED by the rewired gate.
- A real edge (GSR) is **blocked from trading** while unapproved.

## (2) What remains UNPROVEN
- **Live broker behaviour** — reconciliation/executor are unit-tested against mocks, not a live MT5
  fill (slippage, partial fills, broker rejects, SL-attach-with-entry).
- **Shadow soak** — the ≥100-signal / 30-day / multi-volatility run has not executed.
- **Restart/idempotency under real conditions** — duplicate-order prevention and state recovery are
  designed but not exercised against a live terminal.
- **Any strategy's live profitability** — GSR replicated in research (Sharpe 1.43) but is NOT a
  deployable-approved contract; trend/carry remain NEEDS_REPLICATION.
- **Legacy path** — `live_trader.py --broker mt5` still exists and does **not** route through
  `authorize()`; its guarantees are unproven and it must be retired or wrapped.

## (3) Remaining production risks
1. **Legacy `live_trader.py` — RETIRED at the broker boundary.** `MT5Broker.place_order` now fails
   closed via `execution_safety/execution_guard.py`: no entry submits unless the authorized executor
   armed it, and the legacy path never arms (proven: `test_legacy_retired.py`, 3/3; guard-missing also
   blocks). Residual: protective *close* paths are intentionally left unguarded (risk-reducing), and
   the guard lives at the broker chokepoint — deleting/​bypassing it is the remaining way to reopen the
   hole, so it is change-controlled. The old *source* still exists but can no longer place an entry.
2. **3 open BTC positions** (magic 770001), unledgered, no TP, ~20% stops. Human-classify + close.
3. **Auto-relaunch on the VPS** (Task Scheduler/Startup) may restart the legacy bot. Verify + disable.
4. **Broker-side stop-attach not yet verified on a live fill** — a naked fill is the residual failure
   mode; reconciliation blocks new entries but a human must fix the naked position.
5. **No live executor is wired** — by design; nothing can place an order today, which is the safe state.

## (4) What MUST happen before the FIRST shadow trade
1. Human completes the **Stage-0 freeze** on the VPS (AutoTrading off, stop legacy process, disable
   auto-relaunch, save logs) — see [RUNBOOK_EMERGENCY_STOP.md](RUNBOOK_EMERGENCY_STOP.md).
2. **Retire or wrap** `live_trader.py --broker mt5` so no code reaches MT5 except via `authorize()`.
3. **Classify + resolve** the 3 BTC orphans — [RUNBOOK_ORPHAN_POSITION.md](RUNBOOK_ORPHAN_POSITION.md).
4. Wire the shadow runner to the live MT5 read-only feed (quotes + positions), **no order rights**.
5. Confirm reconciliation reads real broker snapshots and that `protective_stop_monitor` sees live SLs.
6. Then run the **shadow soak** (≥100 signals / 30 days). Shadow ⇒ no orders, ever, in this phase.

Live/demo *order placement* additionally requires everything in [RUNBOOK_DEMO_START.md](RUNBOOK_DEMO_START.md)
plus explicit human + Review Board approval (Stage 12). **Not authorized now.**

## Verdict
The rewired pathway is **fail-closed and safe for building/wiring a shadow harness.** It is **NOT** yet
safe for shadow *trading against a live feed* until items (4).1–(4).6 are done, and it is **NOT**
approved for any order placement. The platform is in a clean, frozen, fully-blocked state:
**nothing can place a trade.** Stopping here per directive; awaiting human approval to proceed.
