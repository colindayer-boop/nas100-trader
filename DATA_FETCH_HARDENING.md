# Data-Fetch Hardening — live_trader.py

**Design principle:** Never crash on external data failure. Degrade gracefully — log a warning, skip the symbol/session, and continue. A trading bot that crashes on a missing bar is worse than one that skips a trade.

## Fixes Applied This Round

### 1. `get_gex_levels()` — spot price None/NaN guard (~line 195)
**File:** `live_trader.py`  
**What was added:** After `spot = float(ticker.fast_info["lastPrice"])`, an explicit check for `None`, `NaN`, or non-positive spot price. Logs a warning and returns `(None, None, None, None)` early instead of computing garbage GEX from invalid inputs.  
**Note:** The outer `try/except` already catches any exception and returns the 4-tuple of Nones. The explicit guard adds diagnostic clarity — the warning pinpoints the failure to an invalid spot price rather than a generic exception.

### 2. `run_xsmom()` — get_bars None/empty guard (~line 714)
**File:** `live_trader.py`  
**What was added:** The original `d = broker.get_bars(sym, "1Day", 400)["Close"].().dropna()` was a chained expression that raised `TypeError` if `get_bars()` returned `None`. Now split into:
```python
data = broker.get_bars(sym, "1Day", 400)
if data is None or data.empty:
    logger.warning(f"xsmom {sym}: get_bars returned None/empty, skipping")
    continue
d = data["Close"].dropna()
```
**Strategy logic unchanged:** momentum scoring, ranking, allocation — all identical.

### 3. `run_sweep_basket()` — documentation of existing guard (~line 923)
**File:** `live_trader.py`  
**What was done:** Added clarifying comments. No code change needed — the protection was already adequate:
- `_asian_sweep_fires()` has an explicit `if data is None or data.empty: return False, 0.0` guard at the top (line 875).
- The call site in `run_sweep_basket()` is wrapped in `try/except Exception` that logs a warning and `continue`s on any error.

## Already-Hardened Guards (Previous Partial Hardening)

These were already in place before this round:

| Location | Line(s) | Guard |
|---|---|---|
| `get_regime()` VIX download | 146–155 | `if vix.empty or len(vix) < 21` → default bull, VIX=99 |
| `get_regime()` SPY download | 159–168 | `if spy.empty or len(spy) < 200` → default bull |
| `get_regime()` QQQ download | 173–182 | `if qqq.empty or len(qqq) < 200` → default bull |
| `get_regime()` outer try/except | 145, 183 | Catches any yf.download failure → defaults |
| `get_gex_levels()` outer try/except | 193, 250 | Returns `None, None, None, None` on any exception |
| `get_gex_levels()` empty exps | 204 | `if not exps: return None, None, None, None` |
| `get_gex_levels()` empty gex dict | 238 | `if not gex_by_strike: return None, None, None, None` |
| `run_asian_sweep()` data fetch | 260–262 | `if data is None or data.empty: return` |
| `run_gold_sweep()` data fetch | 345–347 | `if data is None or data.empty: return` |
| `run_asian_sweep()` per-symbol loop | 488–490 | `if data is None or data.empty: continue` |
| GEX-based filter in asian sweep | 299–300 | `(net_gex is None) or ...` — treats None as permissive |
| `run_orb()` data fetch | 563–565 | `if data is None or data.empty: return` |
| `run_btc()` hourly data | 621–623 | `if data is None or data.empty: return` |
| `run_btc()` BTC tz check | 625 | `if data.index.tz is None: data.index = ...` |
| `run_btc()` daily trend data | 661–663 | `if daily is None or daily.empty: ... return` |
| `run_btctrend()` daily data | 831–833 | `if daily is None or daily.empty: ... return` |
| `run_overnight()` bars | 790–792 | `if _ovn_bars is None or _ovn_bars.empty: ... return` |
| `_asian_sweep_fires()` | 875–876 | `if data is None or data.empty: return False, 0.0` |
| `run_sweep_basket()` try/except | 924–927 | Catches exceptions per-symbol, logs warning, continues |
| `run_xsmom()` try/except | 714–720 | Catches per-symbol exceptions, logs warning, continues |
| `run_xsmom()` insufficient bars | 722 | `if len(d) < 260: ... continue` |
| `run_xsmom()` insufficient scores | 724 | `if len(scores) < 4: ... return` |
| `run_xsmom()` price fetch try/except | 741–743 | Catches per-symbol price fetch failure |

## What Was NOT Changed

- No strategy logic, risk calculations, position sizing, or execution flow was modified.
- Only defensive guards (None checks, empty checks) and diagnostic logging were added.
- `get_gex_levels()` still returns the same `(None, None, None, None)` sentinel on failure — callers already check for None.

## Full Re-Audit (2026-07-09)

Complete line-by-line verification of all 33 `.iloc[-N]` accesses in `live_trader.py`
(1039 lines). Every access was traced to its preceding guard:

| Function | Guard | Guard Line |
|----------|-------|:----------:|
| `get_regime()` VIX | try/except + `vix.empty or len(vix) < 21` | L149 |
| `get_regime()` SPY | try/except + `spy.empty or len(spy) < 200` | L162 |
| `get_regime()` QQQ | try/except + `qqq.empty or len(qqq) < 200` | L176 |
| `run_s1()` | `data is None or data.empty` → return | L261 |
| `run_s2()` | `data is None or data.empty` → return | L346 |
| `run_s3()` | try/except + `len(d) < 70` → continue | L440–450 |
| `run_s4()` | `data is None or data.empty` → continue (per symbol) | L489 |
| `run_s5()` | `data is None or data.empty` → return | L564 |
| `run_btc()` hourly | `data is None or data.empty` → return | L622 |
| `run_btc()` daily | `daily is None or daily.empty` → return | L662 |
| `run_xsmom()` bars | try/except + `len(d) < 260` → continue | L716–722 |
| `run_xsmom()` price | try/except → continue | L738–742 |
| `run_overnight()` | try/except + `_ovn_bars None/empty` → return | L791 |
| `run_btc_trend()` | `daily is None or daily.empty` + `len(close) < 30` | L832–836 |
| `_asian_sweep_fires()` | `data is None or data.empty` → `return False, 0.0` | L875–876 |
| `get_gex_levels()` | Full try/except wrapping entire function | L196–250 |

**Result: 0 remaining unguarded accesses. Hardening is complete.**
