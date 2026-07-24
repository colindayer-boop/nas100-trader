# ORDER_LIFECYCLE — one order, end to end, no ambiguity

Traces a single USDCAD rebalance from signal to belief update. Every file, function, identifier and
log entry involved. Where a step is **not yet implemented**, it says so explicitly rather than implying
coverage.

Worked example identifiers (from the 2026-07-25 shadow run, `--config funded`):
`symbol=USDCAD · target_w=0.165 · target_lots=0.08 · magic=880001 · strategy_id=portfolio_multisleeve · version=v1`

---

## 1. Signal generated
- **File** `scripts/portfolio_mt5.py`
- **Functions** `run()` → `resolve_symbols()` → `fetch_daily()` → `target_weights()`
- `resolve_symbols()` maps internal `USDCAD` → broker `USDCAD` (and `OIL`→`WTOIL-PERP`, `COPPER`→`Copper` via `discover()`).
- `fetch_daily()` pulls `mt5.copy_rates_from_pos(sym, TIMEFRAME_D1, 0, 2600)` → 2678 daily bars.
- `target_weights()` computes sleeve weights (TREND `np.sign(px.pct_change(252)).shift(1)` — **lagged**, so no look-ahead), inverse-vol scales, applies the vol target.
- **Output** `w["USDCAD"] = 0.165`, diagnostics `scale=1.242, realized_vol=6.4%, gross=1.10`.
- **Log** stdout line `USDCAD 0.165 0.08 0.00 0.08`; state persisted to `registry/portfolio_state.json` (`intents[]`).

## 2. Belief updated
- **File** `research-lab/lab/inference.py` — `BeliefGraph`, `InferenceEngine.ingest()`, store `registry/belief_graph.json`.
- **Status: NOT WIRED into the live path.** The portfolio's belief was set from backtest evidence offline; `portfolio_mt5.py` passes `inference=lambda s: "ALLOW_PAPER"` (a constant), it does **not** query the belief graph at runtime.
- **Gap.** To close: replace the lambda with `InferenceEngine(...).gate("H_portfolio_multisleeve")`.

## 3. Contract checked
- **File** `execution_safety/strategy_contract.py` — `StrategyRegistry.load()` reads `strategy_contracts/portfolio_multisleeve.json`.
- **Identifiers** `strategy_id=portfolio_multisleeve`, `version=v1`, `status=PAPER_APPROVED`, `approved_trial_ids=["TR-a921975d8eef2571"]`, `approval_actor="human:colindayer (explicit approval)"`, `permitted_symbols=[…19…]`.
- **Checks applied in** `execution_safety/gate.py::authorize()`: contract exists (`NO_CONTRACT`), `may_trade_demo()` (`NOT_PAPER_APPROVED`), version match (`VERSION_MISMATCH`), trial present (`NO_APPROVED_TRIAL`), symbol permitted (`SYMBOL_NOT_PERMITTED`).
- **Observed real rejection:** `BLOCKED COPPER: ['SYMBOL_NOT_PERMITTED']` on 2026-07-25 — the contract lacked the discovered broker name. Contract amended; gate unchanged.

## 4. Promotion checked
- **File** `execution_safety/promotion_gate.py::can_promote()` — rules in `PROMOTION_RULES`.
- **Status: NOT enforced at order time.** Promotion was applied **out of band** (a script set `status=PAPER_APPROVED`). `authorize()` reads the resulting status but does not re-evaluate `can_promote()`.
- **Known deviation:** promotion criteria `min_shadow_signals=100` / `min_shadow_days=30` were **not met** (3 shadow runs, 1 day). Promotion proceeded on explicit human approval. This is a documented override, not a satisfied rule.

## 5. Guardian approved
- **File** `scripts/prop_risk_guardian.py` (`evaluate()`); risk gates also inside `gate.py`.
- **Status: PARTIALLY WIRED.** `portfolio_mt5.py` passes `guardian_ok=True` — a **hardcoded constant**, not a live Guardian call. The gate's own limits *are* enforced (`PYRAMIDING_BLOCKED`, `MAX_CONCURRENT_POSITIONS`, `MISSING_STOP`, `STOP_DISTANCE_IMPLAUSIBLE`, `NO_RISK_BUDGET`).
- **Gap.** To close: call `prop_risk_guardian.evaluate(mt5_snapshot(cfg), …)` and pass its `allow_new_entries`.

## 6. Risk calculated
- **File** `scripts/portfolio_mt5.py` — `notional_per_lot()` → `lots_for()`.
- `notional_per_lot("USDCAD", contract_size=100000, ask=1.37)` = **100,000** (USD-base pair — *not* ×price; this was the 157× bug fixed on 2026-07-25).
- `lots_for` → `raw = 0.165 × 47,577.82 / 100,000 = 0.0785` → rounded to `volume_step` → **0.08 lots**.
- Deterministic sizing inside the gate: `_deterministic_volume(equity, risk_fraction, entry, stop)`.

## 7. Order Intent created
- **File** `execution_safety/gate.py` — dataclass `OrderIntent`, returned inside the decision dict.
- **Fields** `intent_id=OI-pf-USDCAD-<epoch>`, `decision_id=D-pf-USDCAD-<epoch>`, `strategy_id`, `strategy_version`, `symbol`, `direction=+1`, `entry_type="market"`, `requested_entry`, `stop_loss`, `risk_amount`, `risk_fraction`, `calculated_volume`, `magic_number=880001`, `comment="portfolio:funded"`, `created_at`.
- **Invariant** an intent exists **only** on `ALLOW_PAPER`; a BLOCK decision returns no `order_intent` key (test `test_rejected_creates_no_intent`).

## 8. Broker request
- **File** `scripts/portfolio_mt5.py::run()` (live branch) → `mt5.order_send(req)`.
- **Guard** wrapped in `with armed(dec["decision_id"])` — `execution_safety/execution_guard.py::consume_or_block()` raises `ExecutionBlocked` unless armed, and the token is **one-shot**.
- **Request** `{action: TRADE_ACTION_DEAL, symbol: "USDCAD", volume: 0.08, type: ORDER_TYPE_BUY, price: <ask>, deviation: 20, magic: 880001, comment: "portfolio:funded", type_filling: ORDER_FILLING_IOC}`.
- **KNOWN DEFECT:** this request carries **no `sl`/`tp`**. The gate validates a stop, but the portfolio path does not transmit it. **A fill here would be a naked position.** Must be fixed before any fill.

## 9. Broker response
- **Decoded in** `run()` via the `RC` map.
- **Observed 2026-07-25:** `retcode 10018 MARKET_CLOSED` on all 11 intents — **zero fills** (weekend).
- Success would be `10009 DONE`; `10014 INVALID_VOLUME`, `10016 INVALID_STOPS`, `10019 NO_MONEY`, `10027 AUTOTRADING_DISABLED_CLIENT` are the other realistic paths.

## 10. Position ledger
- **File** `execution_safety/position_ledger.py` — `PositionLedger.record_intent()`, store `registry/position_ledger.jsonl` (append-only), orphan check `classify_broker_positions()`.
- **Status: NOT WIRED into the portfolio path.** `portfolio_mt5.py` never calls `record_intent()`. A fill today would be **unledgered → an ORPHAN** by our own policy.
- **Gap.** To close: call `record_intent(intent, trial_ids, decision_id)` immediately after `ALLOW_PAPER`, before `order_send`.

## 11. Exit
- **Status: NOT IMPLEMENTED.** The portfolio is rebalance-driven: the next run computes new targets and the `delta` closes/reduces positions. There is **no** stop-loss exit, no take-profit, and no reconciliation that a position was closed as intended.
- Reconciliation primitives exist (`execution_safety/broker_reconciliation.py::reconcile`, `protective_stop_monitor`) but are **not called** by this path.

## 12. Belief update
- **Status: NOT IMPLEMENTED.** Realised P&L does not flow back into `BeliefGraph`. Closing the loop requires reading closed deals (`mt5.history_deals_get`) and calling `InferenceEngine.ingest()` with realised outcomes.

---

## Verdict of this trace
**The chain is NOT yet unambiguous end-to-end.** Steps 1, 3, 6, 7, 8, 9 are real, implemented and observed. Steps **2, 4, 5, 10, 11, 12 are gaps or constants**, and step 8 has a **blocking defect (no broker-side stop transmitted)**.

**Blocking items before any `--live` fill:**
1. Transmit `sl`/`tp` in the `order_send` request (naked-position risk).
2. Call `PositionLedger.record_intent()` before submitting (else every fill is an orphan).
3. Replace `guardian_ok=True` with a real Guardian call.
4. Replace `inference=lambda: "ALLOW_PAPER"` with a real Belief Graph query.
5. Call `reconcile()` after each fill and block on `MISSING_BROKER_STOP`.

Until 1–5 are done, this is an *auditable prototype*, not an auditable trading system.
