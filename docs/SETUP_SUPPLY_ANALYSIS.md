# SETUP SUPPLY ANALYSIS — regime vs filters vs operations (2026-07-10)

_Statistics only. Data: qqq_hourly_7y.csv spliced with 434 fresh Alpaca
extended-hours bars -> continuous through 2026-07-10. Signal definitions =
exact backtest features (full_yearly) matching live (S1 without bull filter).
GEX gate excluded on BOTH sides (unreconstructable historically). Counts are
bar-level signal events; live trades cap at ~1/day/strategy._

## 30-trading-day signal counts: last 30 td vs 25 historical windows (3y)

| signal | hist mean | median | p25 | min | RECENT 30td | percentile |
|---|---|---|---|---|---|---|
| RAW sweep pattern | 15.1 | 15 | 11 | 7 | **22** | **96th** |
| S1 (full filters, pre-GEX) | 8.6 | 9 | 5 | 0 | **14** | **96th** |
| S4 (full filters, pre-GEX) | 11.4 | 11 | 7 | 0 | **20** | **92nd** |
| S5 ORB break (price-only) | 42.3 | 42 | 37 | 32 | 41 | 48th |
| S5 + volume confirm | 33.4 | 31 | 28 | 23 | 27 | 24th |
| S5 + SPY-bull regime | 32.2 | 30 | 26 | 17 | 27 | 28th |

## Filter survival (share of raw events passing the full filter set)

| funnel stage | historical | recent 30td |
|---|---|---|
| S1 filters (VWAP+EMA50+calm-vol) of sweeps | 57.0% | **63.6%** |
| S4 filters (EMA50>EMA200+calm-vol) of sweeps | 74.3% | **90.9%** |
| S5 volume confirm of ORB breaks | 79.5% | 65.9% |
| S5 SPY-bull of vol-confirmed | 96.2% | 100.0% |

## Verdict

1. **The market DID produce the designed setups — at 3-year highs.** Raw sweeps
   and filtered S1/S4 signals in the last 30 td sit at the 92nd–96th percentile
   of all 3-year windows. S5 supply is normal (24th–48th pct, within range).
2. **The filters are NOT over-rejecting.** Recent survival rates are equal to or
   HIGHER than historical for S1/S4; S5's volume confirm is mildly stricter
   recently (65.9% vs 79.5%) — a market character note, not a malfunction.
3. **The missing trades are OPERATIONAL, not statistical.** ~28 of the last 30
   trading days the live system was non-functional (emoji-crash silent outage,
   timezone bar corruption, naked-order era) or mid-repair. In the ~1–2 clean
   days since parity (07-09), S5 signalled 3x in dry-run — consistent with the
   ~1/day supply measured here.
4. **Unmeasured residual:** the live GEX gate (S1/S4 only) could legitimately
   remove an unknown fraction of the 14/20 pre-GEX signals; historical GEX is
   not reconstructable. S5 carries no GEX gate — its supply numbers are final.

**Implication:** if the coming clean weeks do NOT convert this measured setup
supply (~1 S5 signal/day, ~14 S1-grade sweeps/30td pre-GEX) into live trades,
the fault is in the live path, not the market — and that becomes provable
within days, not months.
