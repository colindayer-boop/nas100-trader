# LIVE_EXECUTION_FREEZE — PHASE 601 Stage 0

**Status: EMERGENCY FREEZE requested. No orders placed/closed by this process. This document is
inspection + manual instructions only.** I cannot reach the Windows VPS or the MT5 terminal from this
machine — the actions below must be performed by a human on the VPS.

## Account
| field | value |
|--|--|
| account type | **DEMO** (Pepperstone-Demo, "Demo Account - Hedge") |
| account number (SHA-256, first 12) | `5676404f075a` |
| broker / server | Pepperstone Group Limited / Pepperstone-Demo |
| deposit | 50,000 USD · balance 48,436.96 · equity ≈ 47,558 |
| account P&L (Reports "Total") | **−1,663.39** |
| AutoTrading (MT5 "Algo Trading") | **ENABLED (green)** — must be disabled (see below) |

## Open positions (from MT5 Trade/History tabs — human to re-confirm live values)
| ticket | symbol | dir | vol | entry | current SL | TP | opened (UTC) | float P&L |
|--|--|--|--|--|--|--|--|--|
| 346174109 | BTCUSD | buy | 0.22 | 65,621.47 | 52,485.18 | none | 2026-07-23 11:48 | ≈ −390 |
| 344793765 | BTCUSD | buy | 0.06 | 66,220.36 | 52,943.07 | none | 2026-07-21 11:48 | ≈ −140 |
| 344259068 | BTCUSD | buy | 0.30 | 64,836.80 | 52,964.24 | none | 2026-07-20 18:39 | ≈ −290 |

Aggregate: **one directional BTC long exposure ≈ 0.58 lots, floating ≈ −800**, no take-profit set,
stops ~19–20% below entry.

## Attribution
| field | value | confidence |
|--|--|--|
| magic number | **770001** | — |
| evidence | MT5 Journal tooltip "Placed by expert, **Expert id 770001**" **AND** `mt5_broker.py:205` hardcodes `"magic": 770001` | **HIGH** — broker metadata matches our code |
| responsible process | `live_trader.py --broker mt5` (this repo), BTC strategy | HIGH |
| specific strategy (comment) | `run_btc` (tag "BTC", sweep) **or** `run_btc_trend` (tag "BTCTREND") | **MEDIUM** — read the position **comment** field to disambiguate |
| why the stop is ~20% wide | does NOT match `run_btc` `STOP_BTC=0.025` (would be ~2.5% → ~63,200). Consistent with `run_btc_trend` (long/flat trend, wider) or an emergency protective floor (`ensure_btc_protection`) | MEDIUM — confirm from comment/logs |

**I do not claim the exact strategy without the position comment or Experts log.** The *account/magic*
attribution is broker-backed and firm.

## Manual freeze instructions (human, on the VPS — do these in order)
1. **Disable AutoTrading:** click the green **Algo Trading** button in MT5 so it turns grey. This stops
   any EA/script from opening or modifying positions.
2. **Save logs before changing anything:** MT5 → Toolbox → **Journal** tab → right-click → Save As;
   repeat for **Experts** tab. Also copy `MQL5/Logs/` and the terminal `Logs/` folder off the VPS.
3. **Stop the Python trader:** find the process — Task Manager → Details → any `python.exe` running
   `live_trader.py`; also check **Task Scheduler** and **Startup** for a scheduled/boot entry that
   relaunches it. Stop it. (Do not delete yet — we need it for the inventory/parity audit.)
4. **Positions:** the 3 BTC longs are **left open** per the "do not close automatically" rule. Risk of
   leaving them open: they float ≈ −800 and have no TP; the 20% stops are far, so further BTC downside
   adds loss until you (a human) decide to close them from the Trade tab (✕ per row). This is a demo —
   no real capital — but they distort any clean read of the rewired system until closed or classified.

## Do-not list (enforced by this recovery)
No orders placed/closed by tooling · MT5 AutoTrading to remain **off** until Stage 12 · no overnight
automated trading · the system must **fail closed** — missing information ⇒ NO TRADE.
