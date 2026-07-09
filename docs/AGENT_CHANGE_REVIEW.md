# AGENT CHANGE REVIEW

_Inspection only. No code edited. Branch: `ai/docs-audit`._

> [!danger] Headline
> The **uncommitted** changes to `live_trader.py` leave it **non-runnable** — it does
> not even parse (Python `SyntaxError`), and separately references `args` before it
> exists (`NameError`). If committed/merged as-is, **every scheduled run on every
> venue fails at startup — zero trades everywhere.**
> These changes are **uncommitted on a side branch**, so the live VPS (which pulls
> `main`) is **not yet affected**. The fix is to NOT ship this as-is.

## 1. Which files were modified?

**Uncommitted (working tree) — the trading-critical ones:**
- `live_trader.py` — modified (+75/−1) — **BROKEN**
- `broker.py` — modified (+7/−2) — parses OK

**Untracked (new, not committed):**
- `docs/NO_REAL_TRADES_ROOT_CAUSE.md` (600 lines) — analysis
- `docs/LIVE_TRADE_REVIEW.md` (599 lines) — analysis
- `.github/workflows/paper-trade.yml`

**Already committed on this branch (inert, not wired in):**
- `risk/` package (`__init__`, `risk_profile_loader`, `challenge_mode`, `funded_mode`, `live_mode`)
- `config/risk_profiles.yaml`
- `docs/RISK_MODE_ARCHITECTURE.md`, `docs/CHALLENGE_VS_FUNDED_VS_LIVE.md`, `docs/PROP_CHALLENGE_PLAYBOOK.md`, plus `ARCHITECTURE_AUDIT.md`, `CODE_MAP.md`, `LIVE_EXECUTION_FLOW.md`

**Referenced but MISSING:** `docs/PEPPERSTONE_VPS_TRACE.md` does not exist.

## 2. What exactly changed?

### `live_trader.py` (uncommitted)
- Added `import time, atexit`.
- **Session lock / 5-min cooldown** (`_LOCK_FILE`, `_check_and_set_lock`): exits(0) if the
  same session ran < 300s ago.
- **`update_risk_state` equity<=0 guard**: returns safe defaults if equity <= 0.
- **Weekend/holiday skip**: non-crypto sessions exit(0) on Sat/Sun.
- **Stale `risk_state.json` migration**: deletes the default state file if a broker-specific one exists.

> [!bug] Two FATAL defects introduced
> - **BUG A — SyntaxError (line 135):** `def update_risk_state(equity, broker_name="default):`
>   — the closing quote of `"default"` is missing → unterminated string → **the file does not parse.**
> - **BUG B — NameError (line 63 & 94):** `_LOCK_FILE = ...f"trader_{args.session}.lock"` and
>   the cooldown message use `args.session` / `args`, but `args = parser.parse_args()` is at
>   **line 999** → referencing `args` at module top raises `NameError` at runtime.
> Verified: `python3 -c "ast.parse(open('live_trader.py').read())"` → **FAILS**. `broker.py` → parses OK.

### `broker.py` (uncommitted)
- Cosmetic import cleanup; added `import json`, `from datetime import datetime, timezone` (**unused**).
- `_load_local_csv`: replaced `tf_tag = "hourly" if tf=="1Hour" else "1min"` with a
  `tf_map` that also handles `"1Day" -> "daily"`. Safe, small improvement.

## 3. Which changes are SAFE infrastructure fixes?
- ✅ `broker.py` CSV `tf_map` (adds `1Day` support to the local-CSV fallback).
- ✅ `update_risk_state` **equity<=0 guard** (genuinely good defensive fix) — *but currently sits on the broken line.*
- ✅ Stale `risk_state.json` migration (low risk).
- ✅ The committed `risk/` mode package + `config/risk_profiles.yaml` + mode docs are **inert** (never imported by `live_trader.py` — grep confirms no `--risk-mode`/`import risk` wiring). They cannot affect trading. Safe to keep dormant.
- ✅ The two investigation docs are analysis only.

## 4. Which changes could affect TRADING behaviour?
- 🔴 **BUG A + BUG B**: catastrophic — the trader cannot start, so **no trades on any live_trader-driven venue** (Alpaca Actions + MT5 VPS) if shipped.
- 🟠 **Session 5-min cooldown**: would `exit(0)` a session that re-ran within 5 min. MT5/Actions run hourly so normally harmless, but it silently skips manual re-runs and any sub-5-min retrigger.
- 🟠 **Weekend skip**: prevents all non-crypto sessions Sat/Sun. Reasonable (markets closed) but a new behavior change — verify it doesn't block the Sunday-evening CFD reopen or overnight logic.
- 🟡 **Stale state deletion**: removes `risk_state.json`, resetting the DD-throttle peak baseline once.

## 5. Which changes should be KEPT?
- Keep `broker.py` `tf_map` fix (drop the two unused imports when convenient).
- Keep the **equity<=0 guard** — but only after Bug A is fixed.
- Keep the weekend-skip and cooldown **ideas**, but only once relocated to run **after** `args = parser.parse_args()` and the string quote is fixed.
- Keep the committed `risk/` package + docs (dormant, harmless).

## 6. Which changes should be REVERTED?
- 🔴 **Revert the current `live_trader.py` working-tree state.** It is fatally broken. Cleanest:
  `git restore live_trader.py` (back to committed `42676fc`), then **re-apply the good parts correctly** (fix the quote; move the lock/cooldown/weekend blocks to *after* argparse).
- `broker.py` may be kept (parses fine); optionally trim the unused `json`/`datetime` imports.
- Do **not** commit the working tree as-is under any circumstances.

## 7. Single highest-priority next fix
**Make `live_trader.py` parse and run again — restore it to a runnable state before anything else.**
- Right now the bot is 100% non-functional (SyntaxError + NameError). Nothing else — risk modes, monitoring, strategy work — matters until the entrypoint starts.
- Minimal fix: (a) restore the missing `"` in `broker_name="default"`; (b) move `_LOCK_FILE` /
  `_check_and_set_lock` / cooldown / weekend-skip to **after** `args = parser.parse_args()`.
- Verify with: `python3 -c "import ast; ast.parse(open('live_trader.py').read()); print('OK')"`
  then a dry run: `python live_trader.py --broker mt5 --session all --dry-run`.

---
### Verification commands used (read-only)
```
git status ; git diff --stat ; git diff broker.py live_trader.py
python3 -c "import ast; ast.parse(open('live_trader.py').read())"   # FAILS (SyntaxError L135)
python3 -c "import ast; ast.parse(open('broker.py').read())"        # OK
grep -n 'args.session' live_trader.py   # L63/94 (top) vs parse_args L999
grep -n 'risk_mode\|import risk' live_trader.py   # none -> risk modes not wired
```
