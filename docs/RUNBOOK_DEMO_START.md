# RUNBOOK — DEMO START (Stage 12, NOT YET AUTHORIZED)

**Do not follow this yet.** Demo execution is blocked until the readiness checklist passes and a human
approves. This documents the *future* controlled-start procedure.

**Preconditions (all required):**
- Shadow soak passed: ≥100 eligible signals, ≥30 days, multiple volatility conditions.
- Live/research parity: zero unexplained divergences.
- Zero orphan positions; zero missing broker-side stops.
- Exactly one strategy with status `PAPER_APPROVED` for the target firm config.

**Initial demo permissions (safety defaults, not optimal sizing):**
one strategy · one symbol · one open position · no pyramiding · risk/trade ≤ 0.10% ·
daily stop ≤ 0.30% · weekly stop ≤ 0.75% · mandatory broker-side stop · no averaging down ·
no auto parameter learning · no overnight unless explicitly validated · kill switch enabled.

**Procedure (when authorized):**
1. Confirm demo account via `authorize(..., account_is_demo=True)` guard.
2. Start the strategy in the pipeline (authorize → reconcile → ledger).
3. Verify each fill reconciles (volume, broker-side SL, magic, comment) before the next signal.
4. Run ≥100 closed demo trades. Promotion requires positive after-cost expectancy, parity, no
   orphans, no missing stops, acceptable slippage, drawdown within simulation envelope, Review Board
   + explicit human approval.
