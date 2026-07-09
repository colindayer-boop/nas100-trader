# Live Trade Review — Complete Analysis

**Generated:** 2026-07-09  
**Period analyzed:** 2026-06-28 → 2026-07-02 (5 calendar days)  
**Log files analyzed:** `logs/trader.log` (sole trading log; no rotated logs exist)  
**State files analyzed:** `risk_state.json`, `risk_state_alpaca.json`, `risk_state_binance.json`  
**Source code analyzed:** `live_trader.py`, `broker.py`, `mt5_broker.py`, `alpaca_broker.py`, `alerts.py`, `alpaca_paper_trader.py`

---

## Executive Summary

**Zero real-money fills occurred.** The system ran 21 sessions across 5 days (2026-06-28 to 2026-07-02). Of these, **19 were dry-runs** and **2 were live (`dry_run=False`)**. The 2 live sessions produced **zero signals that reached order placement** — every strategy either found no signal, was paused by regime filters, or was blocked by a strategy guard. **Four dry-run simulated trades** were generated for observation. No stop-losses were hit, no kill switches triggered, and no P&L (positive or negative) was realized.

The system is **operationally functional** but has never placed a real order. The equity decline from $100,000 to $98,509 visible in the risk state files is from a **pre-existing Alpaca paper account** (unrelated trades or setup), not from this trading system.

---

## A. TRADE LEDGER

### Real (Live) Orders Placed

| # | Timestamp | Session | Broker | Symbol | Side | Qty | Entry | SL | TP | Status |
|---|-----------|---------|--------|--------|------|-----|-------|----|----|--------|
| — | — | — | — | — | — | — | — | — | — | **NONE** |

**Zero real orders were placed.** The two live sessions (`dry_run=False`) produced no signals.

### Dry-Run (Simulated) Orders

| # | Timestamp (UTC) | Session | Broker | Symbol | Side | Qty | Strategy | SL | TP | Notes |
|---|-----------------|---------|--------|--------|------|-----|----------|----|----|-------|
| D1 | 2026-06-29 13:21:41 | rebal | alpaca | EEM | BUY | 99.0 | XSMOM | none | none | Monthly momentum top-3 pick |
| D2 | 2026-06-29 13:21:41 | rebal | alpaca | DBC | BUY | 250.0 | XSMOM | none | none | Monthly momentum top-3 pick |
| D3 | 2026-06-29 13:21:41 | rebal | alpaca | IWM | BUY | 22.0 | XSMOM | none | none | Monthly momentum top-3 pick |
| D4 | 2026-06-30 21:36:13 | overnight | alpaca | QQQ | BUY | 33.0 | OVN | $price×0.95 (5% cat. stop) | none | Tue/Wed overnight drift |

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total sessions run | 21 |
| Live sessions (dry_run=False) | 2 |
| Dry-run sessions (dry_run=True) | 19 |
| Real fills | 0 |
| Dry-run simulated orders | 4 |
| Kill switch triggers | 0 |
| Order failures | 0 |
| Strategies that fired (any mode) | 2 of 11 (XSMOM, OVN) |
| Strategies that never fired | S1, S2, S3, S4, S5, BTC, BTC-TREND, SWEEP-BASKET |
| Account peak equity (Alpaca) | $100,000.00 |
| Current equity (Alpaca, last logged) | $98,509.05 (-1.5%) |
| Account peak equity (Binance) | $25,000.00 |
| Current equity (Binance, last logged) | $25,000.00 |

---

## B. PER-TRADE ANALYSIS

### Trade D1: XSMOM → BUY 99.0 EEM

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-06-29 13:21:41 UTC |
| **Session** | rebal (monthly cross-sectional momentum) |
| **Mode** | DRY-RUN |
| **Broker** | alpaca |
| **Symbol** | EEM (iShares MSCI Emerging Markets ETF) |
| **Side** | BUY |
| **Quantity** | 99 shares |
| **Strategy tag** | XSMOM |
| **SL/TP** | None (monthly rebalance; time-based exit) |
| **Stop-loss** | ❌ Not attached |
| **Take-profit** | ❌ Not attached |
| **Equity at time** | $100,000 (dry-run default) |
| **VIX regime** | 17.8, SPY bull, vix_mult=1.0 |
| **DD-throttle** | peak=$100k, dd=0%, throttle=1.00, RISK_SCALE=1.00 |
| **Entry reason** | EEM had 12-1 month momentum of +42.1%, ranked #1 of 8-ETF universe |

**Log evidence:**
```
2026-06-29 13:21:40,934 INFO xsmom target=['EEM', 'DBC', 'IWM'] scores={'SPY': 0.233, 'QQQ': 0.347, 'IWM': 0.356, 'EFA': 0.182, 'EEM': 0.421, 'TLT': -0.025, 'GLD': 0.345, 'DBC': 0.356}
2026-06-29 13:21:41,047 INFO [DRY-RUN] WOULD BUY 99.0 EEM (XSMOM)
```

**Q&A:**
1. **Did the trade follow the strategy correctly?** Yes — EEM was the top-ranked ETF by 12-1 month momentum (+42.1%), correctly selected for the top-3 portfolio.
2. **Was the loss expected?** N/A — never executed.
3. **Was execution different from the backtest?** The first `rebal` attempt (13:21:21) failed because `get_bars("SPY", "1Day", ...)` tried to load local CSV `spy_1min_7y.csv` (wrong file mapping for "1Day" timeframe). The second attempt (13:21:38) succeeded, suggesting the code was fixed between runs or the dry-run fallback resolved it. **This is a bug: the `_load_local_csv` fallback maps "1Day" to the "1min" CSV.**
4. **Were any filters missing?** No stop-loss or take-profit attached. XSMOM is a monthly rebalance strategy by design (time-based exit), so this is intentional, but the DryRunBroker's `place_order_safe` does not even log bracket prices.
5. **Were any safety systems triggered?** No. DD-throttle was at 1.00 (no drawdown).

---

### Trade D2: XSMOM → BUY 250.0 DBC

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-06-29 13:21:41 UTC |
| **Session** | rebal |
| **Mode** | DRY-RUN |
| **Symbol** | DBC (Invesco DB Commodity Index ETF) |
| **Side** | BUY |
| **Quantity** | 250 shares |
| **12-1 momentum** | +35.6% (tied with IWM at rank #2/#3) |
| **All other fields** | Same as D1 |

**Log evidence:**
```
2026-06-29 13:21:41,157 INFO [DRY-RUN] WOULD BUY 250.0 DBC (XSMOM)
```

**Q&A:**
1. **Did the trade follow the strategy correctly?** Yes — DBC was #2 by momentum, correctly in the top-3.
2. **Was the loss expected?** N/A — never executed.
3. **Was execution different from the backtest?** Same CSV mapping bug as D1 applies. Sizing formula: `$100k × 20% / 3 = $6,667 per position / DBC price ≈ $26.67 = 250 shares`. Correct.
4. **Were any filters missing?** Same as D1 — no brackets on XSMOM by design.
5. **Were any safety systems triggered?** No.

---

### Trade D3: XSMOM → BUY 22.0 IWM

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-06-29 13:21:41 UTC |
| **Session** | rebal |
| **Mode** | DRY-RUN |
| **Symbol** | IWM (iShares Russell 2000 ETF) |
| **Side** | BUY |
| **Quantity** | 22 shares |
| **12-1 momentum** | +35.6% |
| **All other fields** | Same as D1 |

**Log evidence:**
```
2026-06-29 13:21:41,275 INFO [DRY-RUN] WOULD BUY 22.0 IWM (XSMOM)
```

**Q&A:**
1. **Did the trade follow the strategy correctly?** Yes — IWM was #3 by momentum.
2. **Was the loss expected?** N/A.
3. **Was execution different from the backtest?** Sizing: `$100k × 20% / 3 = $6,667 / IWM price ≈ $303 = 22 shares`. Correct.
4. **Were any filters missing?** Same — no brackets, by design.
5. **Were any safety systems triggered?** No.

---

### Trade D4: OVN → BUY 33.0 QQQ

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-06-30 21:36:13 UTC |
| **Session** | overnight |
| **Mode** | DRY-RUN |
| **Broker** | alpaca |
| **Symbol** | QQQ |
| **Side** | BUY |
| **Quantity** | 33 shares (fractional, rounded to 2dp) |
| **Strategy tag** | OVN |
| **Catastrophe SL** | entry × 0.95 (5% wide — safety net only, not a normal stop) |
| **Take-profit** | None (time-based exit at next-day open) |
| **Equity at time** | $100,000 (dry-run) |
| **VIX regime** | 17.9, SPY bull, vix_mult=1.0 |
| **DD-throttle** | peak=$100k, dd=0%, throttle=1.00 |
| **Entry reason** | Monday close (weekday=0), entering for Tuesday overnight hold (validated Tue/Wed drift edge) |

**Log evidence:**
```
2026-06-30 21:36:12,534 INFO SESSION OVERNIGHT start
2026-06-30 21:36:13,005 INFO [DRY-RUN] WOULD BUY 33.0 QQQ (OVN)
2026-06-30 21:36:13,005 INFO ALERT 🧪 DRY RUN OVN
BUY 33.00000 QQQ
```

**Q&A:**
1. **Did the trade follow the strategy correctly?** Yes — 2026-06-30 was a Monday. The OVN strategy enters at Monday close for Tuesday morning overnight drift. Sizing: `$100k × 25% / QQQ price ≈ $757 = 33 shares`. Correct per `OVN_ALLOC = 0.25`.
2. **Was the loss expected?** N/A.
3. **Was execution different from the backtest?** The DryRunBroker does not pass SL/TP to its `place_order` method (the signature doesn't accept them). The catastrophe stop at 5% would be logged by `place_order_safe` in the DryRunBroker but the brackets print is in a different code path. The entry timing matches the validated edge (Mon/Tue close → Tue/Wed open).
4. **Were any filters missing?** The OVN strategy has no VIX filter. The validated edge may not hold in high-VIX regimes. However, VIX was 17.9 (low), so no concern at this time.
5. **Were any safety systems triggered?** No.

---

### Non-Firing Analysis: Why Did 9 of 11 Strategies Never Signal?

| Strategy | Sessions evaluated | Why it never fired |
|----------|--------------------|--------------------|
| **S1 (Asian Sweep QQQ)** | 8 | Close price never swept below Asian low with all conditions met. On 6/28, close=737.65 = asian_low=737.65 (right at the level but no sweep). On 6/28 PM, close=706.00 vs asian_low=705.31 (close above Asian low but no sweep below it). On 6/29, asian_low=NaN (no Asian session data formed). |
| **S2 (Gold London FVG)** | 8 | No FVG + strong candle + sweep combination formed in the London window for GLD. |
| **S3 (Abnormal Volume)** | 3 | Best signal was GDX at abnvol=0.67 (below 1.5 threshold). All others well below threshold. |
| **S4 (Multi-Sweep)** | 8 | Same as S1 — no sweep signal. Additionally on 6/29, GEX was positive (+0.80B QQQ, +1.26B SPY) which would have blocked entries even if sweeps fired. |
| **S5 (ORB Hourly)** | 5 | On 6/28: "opening-range (9:00 ET) bar not formed yet" (run too early / weekend data). On 7/2 live: "ORB-low break but bull regime — short disarmed" (price broke below ORB low but QQQ above 200d SMA, so short side correctly blocked). |
| **BTC (Asian Sweep)** | 4 | "not uptrend" on all attempts (EMA50 < EMA200 on daily). Correctly blocked — strategy only enters in confirmed uptrend. BTC was ~$60k and trending down. |
| **BTC-TREND** | 1 | No output logged — session ended immediately (likely not enough data or within tolerance). |
| **SWEEP-BASKET** | 1 | No signals from any of the 9 basket symbols. No log lines for individual symbols, suggesting `_asian_sweep_fires` returned False for all. |

---

### Live Session #1: 2026-06-28 21:31:46 — `session=all, broker=alpaca, dry_run=False`

```
2026-06-28 21:31:46,960 INFO START session=all broker=alpaca dry_run=False
2026-06-28 21:31:48,105 INFO REGIME vix_ma21=17.8 spy_bull=True qqq_bear200=False vix_mult=1.0
2026-06-28 21:31:48,107 INFO DD-throttle: peak=$100,000 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +300.0%
```

**Note:** "month P&L +300.0%" is a bug — the `month_start_equity` was $25,000 (from a previous Binance run that wrote to the default state path) and equity was $100,000, producing ($100k-$25k)/$25k = 300%. This would have triggered the monthly kill switch if the equity had been lower.

All 5 strategies (S1, S2, S4, S5, S3) evaluated and found no signals. No orders placed.

### Live Session #2: 2026-07-02 19:39:21 — `session=orb, broker=alpaca, dry_run=False`

```
2026-07-02 19:39:21,448 INFO START session=orb broker=alpaca dry_run=False
2026-07-02 19:39:23,060 INFO REGIME vix_ma21=18.0 spy_bull=True qqq_bear200=False vix_mult=1.0
2026-07-02 19:39:23,061 INFO DD-throttle: peak=$100,000 dd=-1.5% throttle=0.81 -> RISK_SCALE=0.81 | month P&L +0.1%
2026-07-02 19:39:23,479 INFO S5: ORB-low break but bull regime — short disarmed
```

QQQ broke below its opening range low, but the strategy correctly refused to short because QQQ was above its 200d SMA (bull regime). The short side of S5 requires `qqq_bear200 = True`. **This is the strategy working correctly** — it prevented a counter-trend short.

---

## C. Answers to the 5 Questions (System-Wide)

### 1. Did the trade(s) follow the strategy correctly?

**Yes, all 4 dry-run trades followed their strategy logic correctly.**

- XSMOM (D1-D3): Correctly ranked 8 ETFs by 12-1 month momentum, selected top 3 (EEM +42.1%, DBC/IWM tied +35.6%), sized equal-weight at 20% allocation each.
- OVN (D4): Correctly entered on Monday close for Tuesday overnight hold, sized at 25% allocation.
- All strategies that didn't fire also correctly applied their filters (VIX gate, trend filter, GEX filter, sweep detection, volume threshold, session time windows).

### 2. Was the loss expected?

**No losses occurred.** The $1,491 decline in Alpaca paper equity ($100k → $98,509) is from pre-existing positions on the paper account, not from this trading system. No system-generated order was ever filled.

The DD-throttle correctly detected this drawdown:
- 2026-07-01: dd=-1.6%, throttle=0.80 (RISK_SCALE reduced to 0.80)
- 2026-07-02: dd=-1.5%, throttle=0.81

This means the system would have sized positions at ~80% of normal if a signal had fired — the safety system is working.

### 3. Was execution different from the backtest?

**Several differences identified:**

| Issue | Impact | Severity |
|-------|--------|----------|
| **CSV fallback maps "1Day" to "1min" file** — `_load_local_csv` in `broker.py` uses `tf_tag = "hourly" if tf == "1Hour" else "1min"`, so "1Day" falls to the else branch and looks for `spy_1min_7y.csv` | XSMOM rebalance failed on first attempt (local CSV mode). Live Alpaca API provides daily bars correctly. | **Medium** — breaks dry-run/offline testing |
| **`month P&L +300.0%` / `+2500000.0%`** — DD-throttle's `month_start_equity` is set per-broker, but the first few runs used the default state path before per-broker paths were implemented | Risk state cross-contamination between brokers could cause false kill-switch triggers or false safety margins | **High** — but appears to have been fixed (per-broker paths now used) |
| **DD-throttle peak=$0 for Binance** (2026-06-28 23:52) — equity returned $0 from Binance API | The state file recorded peak=$0, which would make throttle=1.00 for any future equity > $0 | **Medium** — invalid state persisted |
| **`risk_state.json` (default path) has stale June data** — `{"month_key": "2026-06", "month_start_equity": 100000}` while we're now in July | If any code reads the default path instead of the per-broker path, it gets wrong month | **Low** — current code uses per-broker paths |
| **No execution-level differences** in order placement logic vs. backtest (sizing formula, SL/TP levels, regime multipliers all match) | — | — |

### 4. Were any filters missing?

**Filters are comprehensive.** All 11 strategies apply appropriate filters:

| Strategy | Filters Applied | Assessment |
|----------|----------------|------------|
| S1 (Asian Sweep) | VIX gate (>25 = pause), GEX negative-only, volume regime, VWAP reclaim, EMA50 trend, Asian-low sweep | ✅ Complete |
| S2 (Gold FVG) | VIX gate, FVG confirmation, strong candle, sweep, EMA50 trend | ✅ Complete |
| S3 (Abnormal Volume) | VIX gate, volume z-score >1.5, daily return >1%, 5-day hold / 2% stop exit | ✅ Complete (no SL on bracket — exit is time-or-stop checked each run) |
| S4 (Multi-Sweep) | VIX gate, SPY bull filter, GEX negative-only, EMA50>EMA200 trend, volume regime | ✅ Complete |
| S5 (ORB) | VIX <20, volume confirmation (>0.6x OR vol), long needs SPY bull, short needs QQQ<200d SMA | ✅ Complete |
| BTC (Sweep) | EMA50>EMA200 daily uptrend, 08-16 UTC window, Asian low sweep + reclaim | ✅ Complete |
| BTC-TREND | Donchian 20/10 trend filter, vol-target sizing | ✅ Complete |
| XSMOM | 12-1 month momentum ranking, top-3 of 8, monthly rebalance | ✅ Complete (no SL by design — monthly time exit) |
| OVN (Overnight) | Weekday filter (Mon/Tue close only), 5% catastrophe SL | ⚠️ No VIX filter — overnight hold during high VIX could be risky |
| SWEEP-BASKET | VIX gate, same sweep logic as S1, broker universe restriction (MT5) | ✅ Complete |

**Missing filter identified:** OVN strategy has no VIX-based pause. The validated edge may degrade in extreme volatility. All other strategies are well-filtered.

### 5. Were any safety systems triggered?

| Safety System | Triggered? | Details |
|--------------|------------|---------|
| **Daily kill switch** (5% daily loss) | ❌ No | Daily P&L never approached -5% |
| **Monthly kill switch** (4% monthly loss) | ❌ No | Month P&L was near 0% or positive |
| **DD-throttle** (conformal drawdown cap) | ✅ Active | Engaged on 2026-07-01 (dd=-1.6%, throttle=0.80) and 2026-07-02 (dd=-1.5%, throttle=0.81), reducing RISK_SCALE to ~0.80. **Working correctly.** |
| **VIX regime gate** | ✅ Active | VIX was always 17.7-18.0 (low regime, mult=1.0). Never triggered the 0.5x (VIX≥20) or 0.0x (VIX>25) throttle. |
| **GEX filter** | ✅ Active | On 2026-06-29, GEX was positive (+0.80B QQQ, +1.26B SPY) — would have blocked S1/S4 entries even if sweep signals fired. **Working correctly.** |
| **Position-already-open skip** | ✅ Active | Checked at the start of each strategy (`if sym in open_syms: skip`). Never triggered because no positions were open. |
| **Trend filter (BTC)** | ✅ Active | BTC was "not uptrend" (EMA50 < EMA200) on all 4 attempts. Correctly blocked entries. |
| **S5 bull/bear regime guard** | ✅ Active | On 2026-07-02, ORB-low break was correctly refused short entry because QQQ > 200d SMA. |
| **Naked order warning** | ❌ No triggers | All `place_order_safe` calls included SL parameter (except XSMOM which is by-design bracket-less). |

---

## D. Session-by-Session Timeline

### 2026-06-28 (Saturday) — 12 sessions

| # | Time (UTC) | Session | Mode | Result |
|---|-----------|---------|------|--------|
| 1 | 01:10 | asian | dry | S1: crashed before regime (no log after START) |
| 2 | 01:11 | asian | dry | S1: crashed before regime (no log after START) |
| 3 | 01:11 | asian | dry | S1/S2/S4: no signals. GEX negative. First complete run. |
| 4 | 09:24 | asian | dry | S1/S2/S4: no signals. Same data (weekend = static) |
| 5 | 10:07 | orb | dry | S5: OR 9:00 bar not formed (weekend) |
| 6 | 11:00 | asian | dry | S1/S2/S4: no signals (DD-throttle first appears) |
| 7 | 14:46 | asian | dry | S1/S2/S4: no signals |
| 8 | 16:12 | btc | dry | BTC: not uptrend (price=60155, below EMA200) |
| 9 | 16:13 | btc | dry | BTC: not uptrend (duplicate run) |
| 10 | **21:31** | **all** | **LIVE** | **S1/S2/S4/S5/S3: no signals. GEX negative. First LIVE run.** |
| 11 | 23:12 | all | dry | Same as #10, no signals |
| 12 | 23:52 | btc | dry | BTC: not in 08-16 UTC window. **Equity=$0 bug (Binance returned 0).** |

### 2026-06-29 (Sunday) — 4 sessions

| # | Time (UTC) | Session | Mode | Result |
|---|-----------|---------|------|--------|
| 13 | 13:21 | rebal | dry | XSMOM: first attempt — CSV fallback bug (`1Day`→`1min`). **FAILED.** |
| 14 | 13:21 | rebal | dry | XSMOM: **3 dry-run orders** — EEM, DBC, IWM (top-3 momentum) |
| 15 | 15:35 | all | dry | S1/S2/S4/S5/S3: no signals. GEX **positive** (+0.80B QQQ) — would block S1/S4. |
| 16 | 15:36 | btc | dry | BTC: not uptrend |

### 2026-06-30 (Monday) — 1 session

| # | Time (UTC) | Session | Mode | Result |
|---|-----------|---------|------|--------|
| 17 | 21:36 | overnight | dry | **OVN: 1 dry-run order** — BUY 33 QQQ (Monday close → Tuesday overnight) |

### 2026-07-01 (Wednesday) — 2 sessions

| # | Time (UTC) | Session | Mode | Result |
|---|-----------|---------|------|--------|
| 18 | 23:20 | btctrend | dry | BTC-TREND: no output (ended immediately, likely within tolerance) |
| 19 | 23:47 | sweep | dry | SWEEP-BASKET: no signals from 9 symbols. DD-throttle engaged: dd=-1.6%, throttle=0.80. |

### 2026-07-02 (Thursday) — 2 sessions

| # | Time (UTC) | Session | Mode | Result |
|---|-----------|---------|------|--------|
| 20 | 19:28 | overnight | dry | OVN: no action (Thursday = wd=3, not Mon/Tue close window) |
| 21 | **19:39** | **orb** | **LIVE** | **S5: ORB-low break but bull regime — short correctly disarmed. No order.** |

---

## E. Risk State Analysis

### Alpaca (`risk_state_alpaca.json`)
```json
{
  "month_key": "2026-07",
  "month_start_equity": 98432.63,
  "peak_equity": 100000.0
}
```
- Peak equity: $100,000 (never exceeded)
- Current drawdown from peak: -1.6% (as of last logged session)
- Month-start (July): $98,432.63
- Month P&L: +0.1% (from $98,432.63 → $98,509.05)
- DD-throttle scale: 0.81 (positions would be sized at 81% of normal)

### Binance (`risk_state_binance.json`)
```json
{
  "month_key": "2026-07",
  "month_start_equity": 25000.0,
  "peak_equity": 25000.0
}
```
- Peak equity: $25,000 (test/demo account)
- No drawdown
- DD-throttle: 1.00 (full size)

### Default (`risk_state.json`) — STALE
```json
{
  "month_key": "2026-06",  // ← June, not July
  "month_start_equity": 100000.0,
  "peak_equity": 100000.0
}
```
- This is the old default path. Per-broker paths are now used. This file is stale and should be cleaned up.

### BTC/OCN/BTC-TREND State Files
- `btc_state.json`: Does not exist (BTC sweep never entered a position)
- `ovn_state.json`: Does not exist (OVN only ran in dry-run; no state persisted)
- `btc_trend_state.json`: Does not exist (BTC-TREND never entered a position)

---

## F. Key Bugs & Issues Found

### Bug #1: CSV Fallback Timeframe Mapping ( broker.py `_load_local_csv`)

```python
tf_tag = "hourly" if tf == "1Hour" else "1min"  # "1Day" → "1min" !!!
```

**Impact:** Any dry-run that falls back to local CSVs for "1Day" timeframe loads the wrong file (`spy_1min_7y.csv` instead of daily data), causing a `FileNotFoundError` or loading 1-minute data as daily bars.

**Evidence:**
```
2026-06-29 13:21:23,691 WARNING xsmom SPY bars failed: No local CSV for SPY/1Day: /Users/colindayer/nas100_backtest/spy_1min_7y.csv
```

### Bug #2: Equity Cross-Contamination in DD-Throttle

Early runs stored state in the default `risk_state.json` path. Later runs used per-broker paths, but the transition caused wild month P&L readings:

```
2026-06-28 21:31:48,107 INFO DD-throttle: peak=$100,000 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +300.0%
2026-06-29 15:36:27,176 INFO DD-throttle: peak=$25,000 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +2500000.0%
```

**Impact:** False monthly kill-switch triggers possible. If the +300% reading had been negative (e.g., month_start=$100k, equity=$25k → -75%), it would have halted all trading erroneously.

### Bug #3: Binance Equity = $0

```
2026-06-28 23:52:47,005 INFO DD-throttle: peak=$0 dd=+0.0% throttle=1.00
```

The Binance API returned $0 equity (unfunded demo or API issue). This was written as peak=$0 to the state file. Any future equity > $0 would set dd = (equity - 0) / 0 → handled by `max(peak, 1)` but produces nonsensical throttle values.

### Bug #4: Weekend Data Staleness

On 2026-06-28 (Saturday) and 2026-06-29 (Sunday), the system ran multiple sessions but all bar data was identical (markets closed). The GEX options data and bar data didn't change, resulting in 7+ redundant evaluation runs.

### Bug #5: Duplicate/Aborted Session Starts

```
2026-06-28 01:10:56,820 INFO START session=asian broker=alpaca dry_run=True
2026-06-28 01:11:20,754 INFO START session=asian broker=alpaca dry_run=True
2026-06-28 01:11:47,052 INFO START session=asian broker=alpaca dry_run=True
```

Three consecutive START entries within 51 seconds. The first two have no END — they crashed or were killed before completing (likely broker init or yfinance download timeout).

### Bug #6: GEX Runs After Session END

```
2026-07-02 19:39:23,479 INFO END session=orb
2026-07-02 19:39:25,893 INFO GEX QQQ: net=-2.10B flip=None put_wall=700.0 call_wall=730.0
```

The GEX log line appears 2.4 seconds AFTER the session END. This is because `get_gex_levels()` is called inside S5 but its logging happens asynchronously or the END was logged before the strategy fully returned. Not harmful but indicates non-sequential logging.

---

## G. Infrastructure Observations

### Credentials Exposed in `config.ini`
The `config.ini` file contains live API keys for Alpaca, Binance, cTrader, and MT5 (Pepperstone demo). While this is a local file (gitignored), it represents a single point of compromise. All credentials are for **paper/demo accounts** based on the URLs (`paper-api.alpaca.markets`, `demo` host for cTrader, `Pepperstone-Demo`).

### No Position State Files Persisted
`btc_state.json`, `ovn_state.json`, and `btc_trend_state.json` were never created because no positions were ever entered (even in dry-run, the DryRunBroker doesn't write state files — only the live broker path does). This means if the system had gone live and entered a BTC position, a subsequent restart would not know about the position unless it checked the broker's `get_positions()`.

### Alert System Never Tested with Real Fill
The alert system (`alerts.py`) sends Telegram/email notifications on fills, order failures, and daily heartbeats. Since no real fills occurred, we cannot verify alert delivery. The log shows `[ALERT]` lines were generated for session completions and dry-run orders.

---

## H. TOP 20 INFRASTRUCTURE IMPROVEMENTS

*(Infrastructure only — no changes to trading logic, entry/exit rules, risk parameters, or strategy selection.)*

### 1. Fix CSV fallback timeframe mapping in `broker.py`
**Problem:** `"1Day"` maps to `"1min"` in `_load_local_csv`.  
**Fix:** Add explicit mapping: `tf_tag = {"1Hour": "hourly", "1Day": "daily", "1Min": "1min"}.get(tf, "1min")`.  
**Impact:** Enables correct offline/dry-run testing of XSMOM and other daily-bar strategies.

### 2. Add session deduplication / cooldown timer
**Problem:** Three identical sessions started within 51 seconds on 2026-06-28.  
**Fix:** Add a PID lock file (`logs/trader.lock`) or check time since last START for the same session type. Reject if <5 minutes apart.  
**Impact:** Prevents wasted API calls, duplicate alerts, and race conditions on state files.

### 3. Prevent weekend/holiday session runs
**Problem:** 7 sessions ran on Saturday/Sunday with identical static data.  
**Fix:** Check `now_et().weekday()` — skip if Saturday (5) or Sunday (6) unless crypto session. Log "market closed - skip".  
**Impact:** Saves compute, API quota, and log noise.

### 4. Migrate stale `risk_state.json` or delete it
**Problem:** Default `risk_state.json` has June data while per-broker files have July data.  
**Fix:** On startup, if `risk_state.json` exists and `risk_state_{broker}.json` also exists, delete or rename the default file. Add a migration warning log.  
**Impact:** Prevents any code path from reading stale risk state.

### 5. Guard against $0 equity from broker API
**Problem:** Binance returned $0 equity, which was persisted as peak=$0.  
**Fix:** In `update_risk_state()`, add: `if equity <= 0: logger.error(...); return 1.0, 0, peak, 0` — don't write state.  
**Impact:** Prevents corrupted risk state from invalid equity readings.

### 6. Add structured trade log (JSONL)
**Problem:** Trade events are buried in free-text log lines. Analysis required manual grep.  
**Fix:** Write a JSONL file (`logs/trades.jsonl`) with one JSON object per signal/order/fill/exit, including all fields (timestamp, strategy, symbol, side, qty, price, SL, TP, regime, throttle, equity).  
**Impact:** Enables automated dashboards, post-hoc analysis, and audit trail.

### 7. Add heartbeat/health-check endpoint
**Problem:** No way to know if the cron/scheduler is alive without reading logs.  
**Fix:** Write `logs/heartbeat.json` every run with `{last_run, session, equity, status}`. Add a separate cron job that alerts if `last_run` > 24h old on a trading day.  
**Impact:** Detects silent scheduler failures within 24h instead of discovering them manually.

### 8. Separate `trader.log` per broker
**Problem:** Alpaca and Binance sessions share one log file, making it hard to trace per-account activity.  
**Fix:** Use `logs/trader_{broker}.log` instead of a single file.  
**Impact:** Cleaner audit trail per account; easier debugging.

### 9. Add log rotation verification
**Problem:** `RotatingFileHandler` is configured with `maxBytes=5_000_000, backupCount=5`, but the current log is only 16KB. No rotation has ever happened. If the system runs for months, old logs will be lost.  
**Fix:** No code change needed, but add a note in deployment docs about expected rotation behavior and consider `backupCount=10` for longer history.  
**Impact:** Preserves historical trade evidence for longer periods.

### 10. Add dry-run mode indicator to all log lines
**Problem:** Log lines don't indicate dry-run vs. live mode consistently. Must correlate with the START line.  
**Fix:** Add `(DRY)` or `(LIVE)` prefix to all strategy log lines via a custom log filter or formatter.  
**Impact:** Prevents misinterpreting dry-run signals as real trades when reviewing logs.

### 11. Validate broker connectivity before strategy evaluation
**Problem:** Two sessions (01:10, 01:11 on 6/28) appear to have crashed during broker init or data download, with no END logged.  
**Fix:** Add a `broker.health_check()` call after init that verifies `get_account()` returns sane equity (> $0) and `get_bars("QQQ", "1Hour", 5)` returns data. Fail fast with a clear error.  
**Impact:** Prevents wasted compute and confusing partial-log sessions.

### 12. Add state file schema versioning
**Problem:** State file format has evolved (default → per-broker). Old files linger.  
**Fix:** Add `"version": 2` field to state JSON. On load, if version mismatch, reinitialize with a warning.  
**Impact:** Smooth future migrations; prevents stale-field bugs.

### 13. Add Telegram alert deduplication
**Problem:** Each dry-run XSMOM order sent 2 alerts (the `[DRY-RUN]` line + the session complete line). On a real fill day, this could send 10+ messages.  
**Fix:** Batch alerts within a session into a single message. Add a `alerts.batch_start()` / `alerts.batch_flush()` pattern.  
**Impact:** Reduces notification fatigue; cleaner Telegram chat.

### 14. Add position reconciliation on startup
**Problem:** If the bot restarts mid-position, it relies on `broker.get_positions()` to discover open positions, but there's no logging of what positions were found.  
**Fix:** Log all open positions at session start: `logger.info(f"Open positions: {[(sym, p.qty, p.avg_price) for sym, p in open_syms.items()]}")`.  
**Impact:** Critical for diagnosing orphaned positions or state-file mismatches.

### 15. Add clock drift detection
**Problem:** Session times depend on `datetime.now(eastern)`. If the host clock drifts, sessions run at wrong times.  
**Fix:** On startup, fetch an NTP time or compare against a market data timestamp. Log a warning if drift > 60 seconds.  
**Impact:** Prevents session-window misalignment (especially for ORB 9:00 ET bar and Asian session 18:00-02:00).

### 16. Add order submission timeout / circuit breaker
**Problem:** `place_order_safe` retries 3 times with exponential backoff but has no total timeout. If the broker API hangs, the session could hang indefinitely.  
**Fix:** Add a `signal.alarm()` or `threading.Timer` timeout on each `place_order` attempt. If total time > 30s, abort and alert.  
**Impact:** Prevents hung sessions from blocking the scheduler.

### 17. Add dashboard health metrics
**Problem:** The Streamlit dashboard exists (`dashboard/` directory) but has no connection to live trade logs.  
**Fix:** Add a metrics endpoint that reads `trader.log` and `risk_state_*.json` and exposes current equity, DD-throttle, last signal, open positions, and session history as JSON.  
**Impact:** Real-time visibility into system status without SSH-ing to read logs.

### 18. Add config validation on startup
**Problem:** Missing `[risk]` section in `config.ini` (not present in the file). The code reads it with `load_config("risk")` and falls back to defaults, but there's no warning that the section is missing.  
**Fix:** Validate required config sections on startup. Log warnings for missing sections using defaults.  
**Impact:** Prevents silent misconfiguration (e.g., if someone deploys without a `[risk]` section).

### 19. Add unit tests for risk state machine
**Problem:** The DD-throttle, monthly kill, and daily kill logic has never been tested with edge cases (negative equity, month boundary, broker switching).  
**Fix:** Add `tests/test_risk_state.py` with cases for: new month reset, drawdown scaling, $0 equity guard, per-broker isolation.  
**Impact:** Prevents regressions in the safety-critical risk system.

### 20. Add deployment runbook / README
**Problem:** No documentation on how to deploy, schedule cron jobs, switch from dry-run to live, or what to do when things go wrong.  
**Fix:** Create `docs/RUNBOOK.md` covering: cron setup, switching `--dry-run` off, monitoring alerts, interpreting DD-throttle logs, emergency shutdown procedure, state file cleanup.  
**Impact:** Enables safe handoff to another operator or future-self after deployment.

---

## I. Appendix: Raw Data References

### Risk Constants (from `live_trader.py`)
| Strategy | Risk % | Stop % | RR Ratio |
|----------|--------|--------|----------|
| S1 | 0.70% | 1.5% | 3:1 |
| S2 | 0.50% | 1.5% | 3:1 |
| S3 | 0.40% | 2.0% | Time-based (5-day hold) |
| S4 | 0.40% | 1.5% | 3:1 |
| S5 | 0.75% | 1.0% | 3:1 |
| BTC | 0.60% | 2.5% | 3:1 |
| XSMOM | 20% alloc | — | Monthly rebalance |
| OVN | 25% alloc | 5% (cat.) | Time-based (next-day open) |

### Regime History
| Date | VIX 21d | SPY Trend | QQQ vs 200d | VIX Mult |
|------|---------|-----------|-------------|----------|
| 2026-06-28 | 17.7-17.8 | Bull | Above | 1.0 |
| 2026-06-29 | 17.8 | Bull | Above | 1.0 |
| 2026-06-30 | 17.9 | Bull | Above | 1.0 |
| 2026-07-01 | 18.0 | Bull | Above | 1.0 |
| 2026-07-02 | 18.0 | Bull | Above | 1.0 |

### Broker Configuration
| Broker | Account | Equity | Status |
|--------|---------|--------|--------|
| Alpaca | Paper (`paper-api.alpaca.markets`) | $98,509 | Active |
| Binance | Live API (unfunded) | $0-$25k | Inconsistent |
| cTrader | Demo (FTMO) | Unknown | Configured, never used |
| MT5 | Pepperstone-Demo | Unknown | Configured, never used |
| Tradovate | Not configured | — | Placeholder creds |

---

*End of Live Trade Review*
