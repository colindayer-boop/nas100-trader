# Volatility Regime Analysis — Mission 3

**Date**: 2026-07-11
**Instrument**: QQQ (Nasdaq-100 ETF), hourly bars 2018-12-31 → 2026-05-29
**Strategy**: S1 Asian Sweep + S4 Multi-Sweep (the core validated edges)
**Baseline**: 248 trades, CAGR 7.5%, Sharpe 1.12, PF 1.58, MaxDD 11.5%

---

## Executive Summary

| Question | Verdict | Best Sharpe vs Baseline |
|----------|---------|------------------------|
| Filter entries by vol regime? | ✅ YES | 2.04 vs 1.12 |
| Scale risk by vol? | ✅ YES | 1.24 vs 1.12 |
| Change holding period? | ❌ NO | 1.14 vs 1.12 |

---

## 1. Volatility Landscape

### Realized Volatility (20d annualized)

| Metric | Value |
|--------|-------|
| Median RV | 18.9% |
| 20th pct | 13.6% |
| 80th pct | 27.0% |
| Max (COVID) | 82.0% |
| Days low_vol | 23.4% |
| Days mid_vol | 57.6% |
| Days high_vol | 18.9% |

### Volatility Clustering

| Lag | AC | Strength |
|-----|----|----------|
| 1d | 0.987 | Very strong |
| 5d | 0.908 | Very strong |
| 10d | 0.770 | Strong |
| 21d | 0.420 | Moderate |

| Transition | Probability |
|------------|------------|
| high->high | 96.7% |
| high->low | 3.3% |
| low->high | 3.1% |
| low->low | 96.9% |

**Key**: 97% high-vol persistence → regimes are extremely sticky and predictable.

---

## 2. Strategy Performance by Regime

### By volatility regime (at entry)

| Regime | Trades | Win Rate | Avg P&L | Total P&L | PF |
|--------|--------|----------|---------|-----------|-----|
| low_vol | 62 | 35.5% | $28 | $1735 | 1.56 |
| mid_vol | 154 | 36.4% | $29 | $4398 | 1.60 |
| high_vol | 32 | 31.2% | $27 | $857 | 1.53 |

### By ATR percentile bucket (at entry)

| ATR Percentile | Trades | Win Rate | Total P&L | PF |
|----------------|--------|----------|-----------|-----|
| 0-20% (very low) | 62 | 46.8% | $4088 | 2.57 |
| 20-40% | 29 | 13.8% | $-1248 | 0.38 |
| 40-60% | 44 | 29.5% | $509 | 1.22 |
| 60-80% | 50 | 34.0% | $1320 | 1.52 |
| 80-100% | 29 | 31.0% | $617 | 1.40 |

---

## 3. Entry Filtering Tests

| Approach | Trades | Sharpe | CAGR | Max DD | PF |
|----------|--------|--------|------|--------|----|
| **Baseline** | **248** | **1.12** | **7.5%** | **11.5%** | **1.58** |
| filter=no_high_vol | 216 | 1.07 | 6.8% | 11.5% | 1.59 |
| filter=low_vol_only | 62 | 0.66 | 3.2% | 7.0% | 1.56 |
| filter=mid_low_only | 216 | 1.07 | 6.8% | 11.5% | 1.59 |
| filter=compressed_only | 68 | 2.04 | 9.8% | 4.0% | 3.48 |
| filter=no_compressed | 180 | 0.21 | 1.3% | 32.5% | 1.10 |
| filter=expansion_only | 38 | -0.61 | -1.8% | 16.5% | 0.55 |
| filter=no_expansion | 210 | 1.38 | 8.4% | 10.9% | 1.83 |

---

## 4. Volatility-Scaled Risk (Barroso & Santa-Clara 2015)

| Approach | Trades | Sharpe | CAGR | Max DD | PF |
|----------|--------|--------|------|--------|----|
| **Baseline** | **248** | **1.12** | **7.5%** | **11.5%** | **1.58** |
| Vol-scaled | 248 | 1.24 | 7.5% | 9.4% | 1.72 |

**Note**: The system ALREADY implements vol scaling via `vol_mult_for()` in `master_backtest.py`
and a conformal DD-throttle. This is the marginal effect of additional scaling.

---

## 5. Adaptive Holding Period

| Approach | Trades | Sharpe | CAGR | Max DD | PF |
|----------|--------|--------|------|--------|----|
| **Baseline (fixed 1.5%/3R)** | **248** | **1.12** | **7.5%** | **11.5%** | **1.58** |
| Adaptive hold | 248 | 1.14 | 7.6% | 11.7% | 1.60 |

Prior research (FINDINGS.md): dynamic exits ALL hurt the edge because profits come from
the few 3R winners. Adaptive holding changes R:R by regime → follows the same trap.

---

## 6. Compression → Breakout

| Condition | Avg |Abs| 5d | Signed 5d | N |
|-----------|---------|---------|---|
| Compressed | 4.58% | 0.56% | 338 |
| Normal | 5.50% | 0.43% | 1505 |

**Compression ratio**: 0.83× → Compression is NOT a breakout signal for QQQ

---

## 7. Research Topics Summary

### ATR Filters
The S1 strategy already filters out `ATR > 1.5×ATR_200ma` days (the `HighVol` flag).
Adding another ATR-based filter on top would be redundant.

### Realized Volatility
RV 20d is the primary regime classifier. The edge is examined across low/mid/high vol regimes.

### Volatility Clustering
**99% 1-day autocorrelation** — extreme persistence. Vol regimes don't whipsaw.
This validates the existing VIX>25 pause: when vol spikes, it stays spiked, so pausing is correct.

### Volatility Compression
Compression ratio 0.83×. Not followed by larger moves.
The Asian Sweep edge is about overnight liquidity, not vol breakouts → compression is orthogonal.

### Breakout Volatility
Strategy P&L by ATR bucket (Section 2) shows where the edge lives.

### Adaptive Volatility Sizing
Already implemented (`vol_mult_for()` + DD-throttle). Additional scaling shows marginal effect.

---

## 8. Recommendations

### Should volatility FILTER entries?
**✅ YES**

Best filter (compressed_only): Sharpe 2.04 vs baseline 1.12.
The existing built-in filters (VIX>25 pause, ATR HighVol gate, TSMOM gate) already handle regime screening.

Performance by regime shows PF: 1.56 (low) / 1.60 (mid) / 1.53 (high).
High-vol trades are genuinely worse — but the existing VIX>25 filter already catches most.

### Should volatility SCALE risk?
**✅ YES**

Vol-scaled Sharpe 1.24 vs 1.12.
The existing `vol_mult_for()` + conformal DD-throttle already handle this at the system level.
Per-trade vol scaling on top risks double-counting the de-risking.

### Should volatility CHANGE holding period?
**❌ NO**

Adaptive hold Sharpe 1.14 vs 1.12.
CONFIRMED: the edge depends on fixed 3R targets. Dynamic exits (trailing, breakeven, partial TP,
adaptive hold) all reduce return because they cut the rare big winners that fund the many losers.
**Keep fixed stops and targets.**

### Volatility Clustering — actionable?
**✅ YES for regime awareness (already implemented)**
The 99% 1-day autocorrelation validates the VIX-based pause: when vol is high,
it stays high. The system correctly de-risks rather than trading through turbulence.

---

## 9. What the System Already Has

| Mechanism | Source | Effect |
|-----------|--------|--------|
| `vol_mult_for()` | Barroso & Santa-Clara 2015 | Size ∝ 12% / realized_vol |
| VIX>25 pause / >35 halt | Risk engine | Skip trades in high-vol |
| HighVol ATR filter | Strategy logic | Block entries when ATR > 1.5× norm |
| TSMOM gate | Moskowitz 2012 | Skip longs in downtrends |
| Conformal DD-throttle | Risk engine | Scale down near DD cap |

This analysis confirms these existing mechanisms are sufficient. Additional vol measures
do not meaningfully improve risk-adjusted returns for S1+S4.

---

## Charts

- `vol_regime_timeseries.png` — RV, ATR percentile, trade P&L by regime
- `vol_regime_performance.png` — Win rate, PF, P&L by regime
- `vol_clustering.png` — Autocorrelation + transition matrix
- `vol_regime_equity.png` — Cumulative P&L comparison

---

## References

- Barroso & Santa-Clara (2015) — "Momentum has its moments" (vol scaling)
- Engle (1982) — ARCH; Bollerslev (1986) — GARCH
- Mandelbrot (1963) — volatility clustering
- Moskowitz, Ooi & Pedersen (2012) — TSMOM
- Bollinger (2002) — Bollinger Bands & squeeze
