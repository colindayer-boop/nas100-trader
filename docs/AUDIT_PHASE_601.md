# AUDIT_PHASE_601 — evidence for every readiness claim

Each claim links to the test that proves it, the file that implements it, how it can still fail, and
the command to reproduce the proof. Run all from the repo root.

Reproduce everything:
```
python3 execution_safety/test_fail_closed.py      # 14
python3 -m execution_safety.test_recovery         # 7
python3 execution_safety/test_legacy_retired.py   # 3
python3 execution_safety/test_promotion.py        # 3
python3 test_mt5_reconnect.py ; python3 test_emergency_protection.py
```

| # | Claim | Proven by (test) | Implemented in (file) | How it can still fail | Reproduce |
|--|--|--|--|--|--|
| 1 | A signal cannot call a broker | `test_signal_has_no_broker_access` | `gate.py` (no broker import) | someone adds a broker import to gate.py | `test_fail_closed.py` |
| 2 | No contract ⇒ block | `test_no_contract_blocks` | `gate.py: authorize()` step 1 | registry returns a stale contract from disk | `test_fail_closed.py` |
| 3 | Not PAPER_APPROVED ⇒ block | `test_not_paper_approved_blocks` | `strategy_contract.py: may_trade_demo` | a contract file edited to PAPER_APPROVED by hand | `test_fail_closed.py` |
| 4 | Version mismatch ⇒ block | `test_version_mismatch_blocks` | `gate.py` step 3 | signal + contract both carry a wrong shared version | `test_fail_closed.py` |
| 5 | No approved trial ⇒ block | `test_no_trial_blocks` | `gate.py` step 4 | a fake trial id placed in the contract | `test_fail_closed.py` |
| 6 | Missing broker stop ⇒ block | `test_missing_stop_blocks` | `gate.py` step 6 | signal carries a nonzero but wrong stop | `test_fail_closed.py` |
| 7 | **20% BTC stop ⇒ block** | `test_implausible_stop_blocks` | `gate.py` (`>0.15` check) | threshold mis-set; a 14% stop passes | `test_fail_closed.py` |
| 8 | Guardian veto final | `test_guardian_veto_cannot_be_overridden` | `gate.py` step 10 | caller passes `guardian_ok=True` incorrectly | `test_fail_closed.py` |
| 9 | Strong belief can't override risk | `test_inference_block_cannot_be_averaged_away` | `gate.py` (any-fail ⇒ block) | future code averages scores before the gate | `test_fail_closed.py` |
| 10 | Demo/real guard | `test_real_account_needs_live_approved` | `gate.py` status gate | `account_is_demo` passed wrong by caller | `test_fail_closed.py` |
| 11 | Rejected ⇒ no intent | `test_rejected_creates_no_intent` | `gate.py` (intent only on ALLOW) | — | `test_fail_closed.py` |
| 12 | End-to-end shadow pass | `test_end_to_end_pass_creates_shadow_intent` | `gate.py`, `shadow.py` | — | `test_fail_closed.py` |
| 13 | Prop breach ⇒ block | `test_prop_blocks_when_trade_would_breach_daily` | `prop_objective.py: survival_check` | firm config wrong/missing (fails closed to None) | `test_recovery.py` |
| 14 | Missing broker stop ⇒ CRITICAL | `test_missing_broker_stop_is_critical` | `broker_reconciliation.py: reconcile` | broker reports a stale SL | `test_recovery.py` |
| 15 | Naked position ⇒ block new | `test_naked_position_blocks_new_entries` | `broker_reconciliation.py: protective_stop_monitor` | monitor not called each cycle | `test_recovery.py` |
| 16 | Orphan ⇒ block all | `test_orphan_position_blocks_all` | `position_ledger.py: classify_broker_positions` | ledger falsely claims a position | `test_recovery.py` |
| 17 | Shadow never places | `test_shadow_never_places_even_on_allow` | `shadow.py` (`placed_order=False`) | a real executor wired without the shadow flag | `test_recovery.py` |
| 18 | **3/3 BTC trades blocked** | `test_parity_blocks_the_btc_trades` | `shadow.py: parity_replay` | — | `test_recovery.py` |
| 19 | **Legacy path retired** | `test_mt5_place_order_blocked_when_unarmed` | `mt5_broker.py` guard + `execution_guard.py` | guard import bypassed / removed (import failure also blocks) | `test_legacy_retired.py` |
| 20 | Arming is one-shot | `test_armed_allows_exactly_once` | `execution_guard.py` | thread-local reused across threads | `test_legacy_retired.py` |
| 21 | Promotion rule blocks GSR | `test_gsr_today_not_eligible` | `promotion_gate.py` | thresholds lowered without review | `test_promotion.py` |
| 22 | Existing broker guards intact | `test_mt5_reconnect.py` (OK) | `mt5_broker.py` | — | `python3 test_mt5_reconnect.py` |

## Residual, honestly stated
- Every proof above is against **mocks**, not a live MT5 fill. Claims 14–18 depend on the executor
  actually reading real broker snapshots — that wiring is not built and not proven live.
- The guard (claim 19) retires the `MT5Broker.place_order` **entry** path. Protective **close** paths
  are intentionally left unguarded (reducing risk must never be blocked) — a deliberate, documented
  fail-safe, not a hole.
- No test can prove a strategy is profitable live. Promotion (claim 21) requires the shadow soak,
  which has not run.
