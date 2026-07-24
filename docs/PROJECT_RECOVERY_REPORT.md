# PROJECT_RECOVERY_REPORT — PHASE 601

Objective: make unsupported trading **technically impossible**; fail closed. No orders were placed or
closed, and MT5 AutoTrading was **not** enabled by this work.

## The eight mandated questions
1. **What process created the BTC positions?** `live_trader.py --broker mt5` (this repo), via
   `run_btc`/`run_btc_trend`. Evidence: MT5 Journal "Placed by **Expert id 770001**" matches the
   hardcoded `"magic": 770001` in `mt5_broker.py:205`. **HIGH confidence** (broker-metadata-backed).
2. **Why were multiple BTC positions permitted?** No concurrent-position or aggregate-exposure gate
   existed on the live path. Three separate buys accreted into one ~0.58-lot BTC long. The rewire now
   treats correlated same-symbol positions as one exposure and blocks pyramiding unless the contract
   allows it (`test_pyramiding_blocked`).
3. **Why was the stop distance so large?** The ~20% stop (65k→52k) does **not** match `run_btc`'s
   `STOP_BTC=2.5%`; it is consistent with the trend/emergency-floor path. Regardless of cause, a stop
   that wide is now **rejected** as `STOP_DISTANCE_IMPLAUSIBLE` (`test_implausible_stop_blocks`).
4. **Which safeguards were absent or bypassed?** (a) no strategy-contract/approval check; (b) no
   demo-account guard on `live_trader.py --broker mt5`; (c) no version/trial linkage; (d) no
   concurrent/correlated-exposure limit; (e) no plausibility check on stop distance. All five are now
   enforced by `authorize()`.
5. **Would the rewired system block the same trade?** **Yes — at four independent gates:** no
   PAPER_APPROVED contract, no approved trial, symbol not permitted, and implausible stop distance.
   Any one blocks; all four fire. Proven by the fail-closed test suite (14/14).
6. **Which exact strategy is eligible for shadow mode?** **None yet.** All statuses are conservative
   (RESEARCH_ONLY / SUSPENDED / NEEDS_REPLICATION). Trend/carry are the only plausible candidates and
   must first get a frozen executable version + a passing pre-registered trial.
7. **What evidence is still missing?** For BTC: the position **comment** field + Experts log (to fix
   the exact strategy). For trend/carry: a frozen `code_commit` and a linked approved trial. For all:
   the Stage 5 prop-firm simulation and Stage 11 shadow soak.
8. **What must happen before demo execution resumes?** Complete Stages 5 (prop objective), 7 (broker
   reconciliation / broker-side stop confirmation), 8 (position ledger + orphan policy), 10 (parity
   audit), 11 (≥100 signals / 30 days shadow), then human + Review Board approval per Stage 12.

## What is complete (this pass)
- **Stage 0 Freeze** — [LIVE_EXECUTION_FREEZE.md](LIVE_EXECUTION_FREEZE.md) (positions, attribution, manual VPS freeze steps).
- **Stage 1 Inventory** — [EXECUTION_INVENTORY.md](EXECUTION_INVENTORY.md) (every execution-capable component).
- **Stage 2 Contracts** — `execution_safety/strategy_contract.py` + 5 conservative contract files.
- **Stages 4/6/9 core** — `execution_safety/gate.py`: the fail-closed `authorize()` pipeline (contract → version → trial → symbol → stop → limits → risk → inference → Guardian), OrderIntent, deterministic sizing, shadow mode.
- **Stage 13** — [STRATEGY_APPROVAL_MATRIX.md](STRATEGY_APPROVAL_MATRIX.md).
- **Tests** — `execution_safety/test_fail_closed.py`: **14/14** guarantees proven, incl. the BTC-bug stop, guardian veto, demo/real guard, "signal cannot touch a broker", and end-to-end shadow pass.

## What remains (sequenced, not yet built)
Stage 5 prop objective engine · Stage 7 broker reconciliation + broker-side-stop confirmation ·
Stage 8 immutable position ledger + orphan policy · Stage 10 live/research parity audit ·
Stage 11 shadow soak (≥100 signals / 30 days) · Stage 12 controlled demo · runbooks
(EMERGENCY_STOP / DEMO_START / ORPHAN_POSITION).

## Current safety state
The new pathway **fails closed**: with today's contracts, `authorize()` returns BLOCK for every
strategy. Unsupported trading through the rewired path is not possible. **The legacy `live_trader.py`
path still exists and must be retired/routed through `authorize()` before any restart** — until then,
keep MT5 AutoTrading OFF (Stage 0).
