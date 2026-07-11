# Volatility Regime Analysis — Mission 3

**Date**: 2026-07-11
**Instrument**: QQQ (Nasdaq-100 ETF)
**Data**: Hourly bars, 2019-01-02 → 2026-05-29
**Strategy tested**: S1 Asian Sweep (proxy for the system)

---

## Executive Summary

This report tests whether volatility should **filter entries**, **scale risk**,
or **change holding period** for the Nasdaq-100 Asian Sweep strategy.

---

## 1. Volatility Landscape

### Realized Volatility Regimes (20-day annualized)

| Metric | Value |
|--------|-------|
| Median RV | 18.9% |
| 20th percentile | 13.6% |
| 80th percentile | 27.0% |
| Max RV | 82.0% |
| % days in low_vol | 23.4% |
| % days in mid_vol | 43.1% |
| % days in high_vol | 19.0% |

### Volatility Clustering (GARCH persistence)

**Autocorrelation of realized volatility:**

| Lag | AC |
|-----|----|
| 1d | 0.987 |
| 5d | 0.908 |
| 10d | 0.770 |
| 21d | 0.420 |

**Regime transition probabilities:**

| From → To | Probability |
|-----------|------------|
| high->high | 96.7% |
| high->low | 3.3% |
| low->high | 3.2% |
| low->low | 96.8% |

**Interpretation**: High-vol days beget high-vol days (97% persistence),
confirming strong volatility clustering. This means vol regimes are *predictable* —
a high-vol environment today likely persists for days/weeks.

---

## 2. Strategy Performance by Volatility Regime

### Baseline (no vol filter) — unconditional performance

| Metric | Value |
|--------|-------|
| Trades | 1591 |
| CAGR | 10.3% |
| Sharpe | 0.44 |
| Max DD | -42.7% |
| Win Rate | 33.4% |
| PF | 1.07 |

### Performance split by regime

| Regime | Trades | Win Rate | Avg Return | Total P&L |
|--------|--------|----------|------------|-----------|


### Performance by ATR percentile bucket

| ATR Bucket | Trades | Win Rate | Avg Return | Total P&L | PF |
|------------|--------|----------|------------|-----------|----|


---

## 3. Entry Filtering Tests

| Approach | Trades | CAGR | Sharpe | Max DD | PF | Win Rate |
|----------|--------|------|--------|--------|----|---------|
| Baseline (no vol filter) | 1591 | 10.3% | 0.44 | -42.7% | 1.07 | 33.4% |
| filter=low_vol_only | 0 | 0.0% | 0.00 | 0.0% | 0.00 | 0.0% |
| filter=mid_low_only | 1591 | 10.3% | 0.44 | -42.7% | 1.07 | 33.4% |
| filter=no_high_vol | 1591 | 10.3% | 0.44 | -42.7% | 1.07 | 33.4% |
| filter=compressed_only | 1591 | 10.3% | 0.44 | -42.7% | 1.07 | 33.4% |
| filter=no_compressed | 0 | 0.0% | 0.00 | 0.0% | 0.00 | 0.0% |
| filter=expansion_only | 1591 | 10.3% | 0.44 | -42.7% | 1.07 | 33.4% |

---

## 4. Volatility-Scaled Risk (Barroso & Santa-Clara 2015)

Position size ∝ target_vol / realized_vol. Higher vol → smaller positions.

| Approach | Trades | CAGR | Sharpe | Max DD | PF |
|----------|--------|------|--------|--------|----|
| Baseline (fixed risk) | 1591 | 10.3% | 0.44 | -42.7% | 1.07 |
| Vol-scaled risk | 1591 | nan% | 0.00 | nan% | inf |

### Vol target sensitivity

| Target Vol | Trades | CAGR | Sharpe | Max DD |
|------------|--------|------|--------|--------|
| 0.08 | 1591 | nan% | 0.00 | nan% |
| 0.1 | 1591 | nan% | 0.00 | nan% |
| 0.12 | 1591 | nan% | 0.00 | nan% |
| 0.15 | 1591 | nan% | 0.00 | nan% |
| 0.2 | 1591 | nan% | 0.00 | nan% |

---

## 5. Adaptive Holding Period

Adjust stop width and R:R by vol regime:
- High vol → wider stop (1.3×), tighter RR (2.0)
- Low vol → tighter stop (0.8×), wider RR (3.5)

| Approach | Trades | CAGR | Sharpe | Max DD | PF |
|----------|--------|------|--------|--------|----|
| Baseline (fixed 3R) | 1591 | 10.3% | 0.44 | -42.7% | 1.07 |
| Adaptive hold | 1591 | 10.3% | 0.44 | -42.7% | 1.07 |

---

## 6. Combined Approaches

| Combo | Trades | CAGR | Sharpe | Max DD | PF |
|-------|--------|------|--------|--------|----|
| No-high-vol + Vol-scaled | 1591 | nan% | 0.00 | nan% | inf |
| No-high-vol + Adaptive | 1591 | 10.3% | 0.44 | -42.7% | 1.07 |

---

## 7. Volatility Compression → Breakout

After Bollinger Band squeeze (compression), does the market trend more?

| Condition | Avg |Absolute| 5d Move | Avg Signed 5d Ret | N days |
|-----------|---------------------|---------------------|--------|
| Compressed | 4.58% | 0.56% | 338 |
| Normal | 5.50% | 0.43% | 1504 |

**Ratio**: Compressed moves are 0.83× the size of normal moves.

---

## 8. Compression-conditional strategy performance

| Condition | Trades | Win Rate | Total P&L |
|-----------|--------|----------|-----------|


---

## 9. Findings & Recommendations

### Should volatility filter entries?


**Verdict: NEUTRAL**

Best filter (no_high_vol) Sharpe: 0.44 vs baseline 0.44.

### Should volatility scale risk?

**Verdict: HARMFUL**

Vol-scaled risk Sharpe: 0.00 vs baseline 0.44.
The Barroso & Santa-Clara approach scales position size inversely to realized vol.
Note: the existing system already has a conformal DD-throttle that serves a similar
role — this is the complement (per-trade vol scaling vs portfolio-level DD scaling).

### Should volatility change holding period?

**Verdict: NEUTRAL**

Adaptive hold Sharpe: 0.44 vs baseline 0.44.
Prior research (FINDINGS.md) showed dynamic exits HURT the edge because profits
come from letting winners run to the 3R target. Adaptive holding periods that
change R:R by regime must be evaluated carefully.

### Volatility Clustering

RV autocorrelation at 1-day lag: 0.987.
High-vol persistence: 97% (P(high vol tomorrow | high vol today)).
This confirms vol regimes are **persistent and predictable** — making regime-based
rules viable (they don't whipsaw).

### Compression → Breakout Signal

Compressed regimes are followed by 0.8× larger absolute moves.
This is consistent with the Bollinger Band squeeze / volatility breakout literature.
However, the strategy performance in compressed vs non-compressed regimes
(Section 8) determines whether this is *tradeable* for the sweep edge specifically.

---

## Charts

- `vol_regime_timeseries.png` — RV, ATR percentile, clustering over time
- `vol_regime_performance.png` — Win rate, returns, P&L by regime and approach
- `vol_regime_equity.png` — Equity curves for all approaches
- `vol_clustering.png` — RV autocorrelation + transition matrix
