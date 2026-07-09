# STARTUP FIX REPORT

_Branch `ai/docs-audit`. Scope: make `live_trader.py` parse and start. No refactoring,
no strategy/risk/sizing/broker changes._

## Claims from AGENT_CHANGE_REVIEW.md — independently verified

| Claim | Verified? | Evidence |
|---|---|---|
| SyntaxError at line 135 (`broker_name="default)`) | ✅ TRUE | `ast.parse` failed: "unterminated string literal (line 135)" |
| `args.session` used before `parse_args()` (lines 63/94 vs 999) | ✅ TRUE | grep showed module-top references; parse_args at 999 |
| `broker.py` parses fine | ✅ TRUE | `py_compile` OK before and after |

## Fixes applied (exactly two, minimal)

1. **Unterminated string (line 135):**
   `broker_name="default)` → `broker_name="default"` — restores the missing quote.
   The equity<=0 guard inside the function is retained (safe infrastructure).

2. **args-before-parse (lock/cooldown block):** restructured so nothing references
   `args` at module level:
   - `_LOCK_FILE` module constant → `_lock_path(session)` helper.
   - `_create_lock_file/_remove_lock_file/_check_and_set_lock` now take `session` as
     a parameter; `atexit.register(_remove_lock_file, session)` passes it through.
   - Call site (main block, line 1013 — AFTER `parse_args()` at 999) updated to
     `_check_and_set_lock(args.session)`.
   - Added `except SystemExit: raise` so the cooldown's intended `exit(0)` isn't
     swallowed by the blanket exception handler (defensive; SystemExit already
     bypasses `except Exception`, this just makes it explicit).

## Infrastructure improvements KEPT (per review: safe)
- equity<=0 guard in `update_risk_state`
- session lock/cooldown (now correctly placed)
- weekend skip for non-crypto sessions (already after parse_args — untouched)
- stale `risk_state.json` migration (already after parse_args — untouched)
- `broker.py` CSV `tf_map` (1Day support)

## Removed
- Nothing beyond the two startup-blocking defects. No other lines changed.

## Verification (all run, all pass)

```
python3 -c "import ast; ast.parse(open('live_trader.py').read())"   -> PARSES OK
python3 -m py_compile live_trader.py                                 -> COMPILES OK
python3 -m py_compile broker.py                                      -> COMPILES OK
awk 'NR<999 && /args\./' live_trader.py                              -> no matches (no early args use)
python3 live_trader.py --help                                        -> argparse renders, exit 0
python3 live_trader.py --session orb --dry-run                       -> FULL RUN, exit 0
```

Dry-run output proves end-to-end preservation:
- lock created → regime fetched → **DD-throttle applied (RISK_SCALE=0.81)** →
  **S5 ORB evaluated and signalled** → sizing `shares=83.0` →
  **`BUY 83.0 QQQ SL=716.54 TP=745.49`** (broker-side bracket intact) → clean END, exit 0.
- Stale `risk_state.json` migration fired once, as designed.

## Preservation checks
- **Risk constants** (`RISK_*`, `STOP_*`, `RR_*`): `diff` vs HEAD → **IDENTICAL**.
- **Strategy/sizing/order code**: 0 lines matching `run_s*/run_btc/run_overnight/
  run_sweep/place_order/RISK_S/STOP_S` appear in the diff.
- **Diff vs HEAD is now pure insertions (+80/−0)** — the accidental deletion of the
  `def update_risk_state` line is healed; all additions are the (fixed) infra blocks.

## Behavior note (pre-existing design, preserved not changed)
The cooldown lock is **removed at normal exit** (`atexit`), so it guards *concurrent /
crashed* duplicate sessions, not rapid sequential completed runs. That is how the
block was designed; changing it would be refactoring, which is out of scope.

## Status: STARTUP VERIFIED ✅
`live_trader.py` parses, compiles, starts, runs a full session to completion with
strategies, risk, sizing, and broker brackets unchanged.
