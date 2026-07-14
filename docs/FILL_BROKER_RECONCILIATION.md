# FILL ↔ BROKER ↔ RESEARCH RECONCILIATION (measured)

_2026-07-14. Evidence-only; no code change. Sources: logs/fills.csv (2 rows) +
logs/mt5_history.html (MT5 report, account 61552095, parsed UTF-16). Measured values
only; INSUFFICIENT_DATA where evidence is absent. Sample: 2 live strategy fills (both
S5). n=2 -> NO expectancy/win-rate conclusions are drawn._

## 0. What the broker actually holds (MT5 account 61552095)
| time (server UTC+3) | position | symbol | type | vol | open | S/L | T/P | close | swap | profit | comment |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 06-29 20:53 | 331549454/554 | XAUUSD | buy | 0.01 | 4021.x | — | — | +3s | 0 | +0.02/+0.21 | **TEST** |
| 07-07 02:23 | 335629107 | BTCUSD | buy | 0.01 | 64083 | 63122 | 66967 | 02:41 | 0 | -0.28 | **TEST** |
| 07-10 19:48:50 | 339422299 | **NAS100** | buy | 1.2 | 29801.2 | 29502.1 | 30694.1 | 07-13 05:59 | **-18.29** | -358.92 | **S5** |
| 07-14 18:48:48 | 341029450 | **NAS100** | buy | 1.1 | 29636.9 | 29340.1 | 30525.6 | OPEN | 0 | -96.47 (unreal) | **S5** |

The XAUUSD/BTCUSD rows are manual `TEST` orders (0.01 lot) -- correctly ABSENT from the
strategy fill ledger. Only the two **S5 NAS100** trades are strategy trades.

## 1. Fill reconciliation (fills.csv ↔ research signal)
| field | Fill #1 | Fill #2 |
|---|---|---|
| strategy | S5 | S5 |
| ledger symbol / **broker symbol** | QQQ / **NAS100 (US100 CFD)** | QQQ / **NAS100** |
| expected signal time | **INSUFFICIENT_DATA** (signal_timestamp blank) | **INSUFFICIENT_DATA** |
| submitted entry (requested) | 29801.1 | 29637.5 |
| signal_price | 29800.1 | 29636.5 |
| fill price | 29801.2 | 29636.9 |
| stop / target | 29502.099 / 30694.103 | 29340.135 / 30525.595 |
| risk_scale | 0.945 | 0.851 |
| qty (units) | 1.18552 | 1.06512 |

## 2. Broker reconciliation (fills.csv ↔ MT5 history) — MATCH
| check | Fill #1 | Fill #2 |
|---|---|---|
| order_id | 339422299 ✓ | 341029450 ✓ |
| position_id / deal | 266746138 ✓ | 267936208 ✓ |
| fill price ledger vs broker | 29801.2 == 29801.2 ✓ **exact** | 29636.9 == 29636.9 ✓ **exact** |
| stop/target ledger vs broker | 29502.1/30694.1 ✓ | 29340.1/30525.6 ✓ |
| units → lots | 1.18552 → **1.2 lots** | 1.06512 → **1.1 lots** |
| outcome | **STOPPED OUT** @29502.1 (07-13) | OPEN, unreal -96.47 |
Timestamps reconcile: ledger 16:48:50/15:48:49 UTC == broker 19:48:50/18:48:48 UTC+3.

## 3. Slippage analysis (measured, signal→fill)
| | Fill #1 | Fill #2 |
|---|---|---|
| slippage (pts) | +1.1 | +0.4 |
| **slippage (bps)** | **0.37** | **0.13** (favorable — filled below ask) |
Both far below the 3 bps/side research assumption. Submission→fill latency < 1s
(broker order+deal same second). **Signal→submission latency: INSUFFICIENT_DATA**
(signal_timestamp not recorded — the one ledger gap; see §8).

## 4. Spread analysis (measured)
Both fills: bid/ask = 1.0 point on ~29,800 → **spread ≈ 0.34 bps/side**. An order of
magnitude tighter than the 3 bps modeled. Spread is NOT a material cost on US100.

## 5. Commission & swap analysis (measured)
- **Commission: 0.00** on both NAS100 S5 trades (Pepperstone US100 = spread-only). (The
  XAU/BTC test trades showed -0.04…-0.08; not strategy.)
- **Swap (financing): Fill #1 = -18.29** over a Fri 07-10 → Mon 07-13 hold (3 calendar
  days). Fill #2 = 0 (no overnight yet). Derivation: the 1.00% stop move = -358.92 price
  P&L → position notional ≈ $35,785 → swap -18.29 ≈ **-0.051% of notional over 3 days ≈
  ~1.7 bps/day**. **Measured financing (~1.7 bps/day) is LOWER than the 3 bps/day modeled
  in the re-cost** — the model over-estimated financing by ~1.75×. (n=1 financing obs.)
- Total realized loss Fill #1 = price -358.92 + swap -18.29 = **-377.21** (matches the
  report's "largest loss trade -377.21").

## 6. Execution quality score (measured, n=2)
| dimension | result | grade |
|---|---|---|
| fill-price accuracy vs broker | exact to the cent | A |
| spread | ~0.34 bps/side | A |
| slippage | 0.13 / 0.37 bps | A |
| commission | 0 | A |
| financing (weekend hold) | -18.29 (~1.7 bps/day) | the only real cost |
| submission→fill latency | < 1s | A |
**Execution quality: EXCELLENT.** The measured cost story is confirmed: spread/slippage
are negligible on US100; **financing on multi-day/weekend holds is the entire CFD cost.**

## 7. Missing / duplicate trades
- Strategy trades: **2 fills ↔ 2 MT5 S5 positions, 1:1. No missing, no duplicate.**
- The report summary shows "10 trades / 8 loss / PF 0.22" but that pool includes the
  manual XAU/BTC TEST deals and in/out legs; the strategy-relevant subset is the 2 S5
  trades. Full non-strategy deal enumeration: **INSUFFICIENT_DATA** (not needed for the
  strategy reconciliation).

## 8. Unexplained differences & gaps
- **Venue (expected, now concrete):** S5 is validated on **QQQ ETF** (opening range,
  price ~480); it traded as **NAS100 CFD** (~29,801). Mechanism matched (breakout entry,
  1%/3:1 bracket, correct stop/target); **venue did not** (ETF≠CFD). This is the
  documented symbol map (QQQ→US100/NAS100), not a defect — but it is the venue mismatch
  made real.
- **Weekend exposure REALIZED once:** Fill #1 was held Fri→Mon and **stopped out**; the
  weekend-gap risk flagged in WEEKEND_EXPOSURE_AUDIT occurred on the first live S5 trade.
- **Sizing rounds UP to the 0.1-lot step** (1.186→1.2, +1.2%; 1.065→1.1, +3.3%) — a
  small systematic oversize from lot granularity, not a sizing error. Worth noting.
- **signal_timestamp is blank** in both ledger rows → signal→submission latency and
  exact signal-time reconciliation are **INSUFFICIENT_DATA**. (Ledger records the entry
  fine; the signal clock is the missing field.)

## Verdict (measured, n=2)
Both live S5 fills reconcile **exactly** to the broker; execution quality is excellent;
commission is zero; **the sole measured cost is weekend/overnight financing (~1.7 bps/day,
below the 3 bps model)**; the venue is CFD not ETF as designed; and the first S5 trade
realized the weekend-gap stop-out. **No conclusion about S5 expectancy is possible at
n=2 — INSUFFICIENT_DATA.** No missing/duplicate strategy fills. The one ledger
improvement the data points to (record signal_timestamp) is an operational note, not a
change made here.
