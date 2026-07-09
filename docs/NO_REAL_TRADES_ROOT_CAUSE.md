# Root Cause Analysis: Why the Live Trading System Never Placed a Real Order

**Document version:** 1.0  
**Date:** 2026-07-09  
**Analyst:** Senior Trading Systems Engineering Review  
**Scope:** All sessions 2026-06-28 → 2026-07-02 (21 sessions across 5 days)  

---

## Executive Summary

**Zero real orders were placed in 5 days of operation.** The root cause is a convergence of three factors, listed in order of severity:

1. **Primary:** 19 of 21 sessions (90%) were launched with `--dry-run`, which wraps the live broker in a `DryRunBroker` that intercepts every `place_order` call and prints `[DRY-RUN] WOULD BUY…` instead of submitting. The system was overwhelmingly operated in simulation mode.

2. **Secondary:** The 2 sessions that DID run live (`dry_run=False`) encountered legitimate "no signal" conditions — no strategy edge was present in the market data at those moments. The strategy filters (Asian-low sweep, GEX gate, ORB bull/bear regime guard) correctly blocked or found nothing.

3. **Tertiary:** Scheduling and configuration gaps — weekend runs on stale data, a CSV timeframe mapping bug, missing `[risk]` section in `config.ini`, and GitHub Actions workflows whose logs never appeared in the local `trader.log` (suggesting they may not have executed successfully, or their logs were ephemeral).

The system code is **operationally functional** — if a strategy signal had fired during a live session, a real paper order would have been placed on Alpaca. The absence of trades is explained by the absence of signals during live sessions, not by a code path failure.

---

## Question 1: Which Live Sessions Ran (`dry_run=False`)?

**Exactly 2 of 21 sessions ran live.** All others had `--dry-run` on the command line.

### Live Session #1 — Saturday 2026-06-28 21:31:46 UTC

```
2026-06-28 21:31:46,960 INFO START session=all broker=alpaca dry_run=False
2026-06-28 21:31:48,105 INFO REGIME vix_ma21=17.8 spy_bull=True qqq_bear200=False vix_mult=1.0
2026-06-28 21:31:48,107 INFO DD-throttle: peak=$100,000 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +300.0%
```

- **Session type:** `all` (runs S1, S2, S4, S5, S3, + sweep basket)
- **Broker:** Alpaca (paper: `paper-api.alpaca.markets`)
- **Equity:** $100,000.00
- **Result:** All 5+ strategies evaluated; **zero signals found**. See Q2 for details.
- **Note:** This was a **Saturday** — markets closed, all bar data was stale (Friday's close replicated). The `"month P&L +300.0%"` reading is a state-contamination bug (see Q4).

### Live Session #2 — Thursday 2026-07-02 19:39:21 UTC

```
2026-07-02 19:39:21,448 INFO START session=orb broker=alpaca dry_run=False
2026-07-02 19:39:23,060 INFO REGIME vix_ma21=18.0 spy_bull=True qqq_bear200=False vix_mult=1.0
2026-07-02 19:39:23,061 INFO DD-throttle: peak=$100,000 dd=-1.5% throttle=0.81 -> RISK_SCALE=0.81 | month P&L +0.1%
2026-07-02 19:39:23,061 INFO SESSION S5 start
2026-07-02 19:39:23,479 INFO S5: ORB-low break but bull regime — short disarmed
```

- **Session type:** `orb` (runs S5 only)
- **Broker:** Alpaca (paper)
- **Equity:** $98,509.05 (drawdown from peak: -1.5%, DD-throttle engaged at 0.81)
- **Result:** QQQ broke below its opening-range low, but S5's bull/bear regime guard **correctly refused to short** because QQQ was above its 200-day SMA (`qqq_bear200=False`). This is the strategy working as designed.

### Evidence: The `--dry-run` Flag in Code

From `live_trader.py`, the argument parser:

```python
parser.add_argument("--dry-run", action="store_true",
                    help="Print intended orders without placing them")
```

`action="store_true"` means `args.dry_run` defaults to `False`. If `--dry-run` is passed, it becomes `True` and the broker is wrapped:

```python
broker = make_broker(args.broker)
if args.dry_run:
    broker = DryRunBroker(broker)
```

When `DryRunBroker` wraps the real broker, all `place_order` calls are intercepted:

```python
# broker.py — DryRunBroker.place_order
def place_order(self, symbol: str, qty: float, side: str, tag: str):
    msg = f"[DRY-RUN] WOULD {side.upper()} {qty:.1f} {symbol} ({tag})"
    print(msg)
    logger.info(msg)
```

**No order is submitted.** The 4 simulated trades (D1–D4) all logged `[DRY-RUN] WOULD BUY…` confirming this wrapper was active.

---

## Question 2: Why Did No Signal Reach Real Order Placement?

### Live Session #1 (Saturday `session=all`) — Strategy-by-Strategy Trace

| Strategy | Log Line | Why No Signal |
|----------|----------|---------------|
| **S1** (Asian Sweep) | `S1 no signal: close=706.00 asian_low=705.31` | Close was $0.69 **above** the Asian low. A sweep requires `data["Low"] < data["AsianLow"]` AND `data["Close"] > data["AsianLow"]` — the low never penetrated below 705.31. **Correct no-signal.** |
| **S2** (Gold FVG) | `S2 no signal` | No Fair Value Gap + strong candle + sweep combination in the London window for GLD. **Correct.** |
| **S4** (Multi-Sweep) | `S4 QQQ: no signal` / `S4 SPY: no signal` | Same sweep requirement as S1. Neither QQQ nor SPY swept below their Asian lows. **Correct.** |
| **S5** (ORB) | `S5: opening-range (9:00 ET) bar not formed yet` | **Saturday** — the 9:00 ET hourly bar for today doesn't exist because the market is closed. No opening range → no ORB trade possible. **Correct.** |
| **S3** (Abn. Volume) | `S3 QQQ: no signal abnvol=0.02` / all symbols <1.5 σ | Best abnormal volume was GDX at 0.67σ (threshold is >1.5σ). No abnormal volume events. **Correct.** |

### Live Session #2 (Thursday `session=orb`) — Strategy Trace

| Strategy | Log Line | Why No Signal |
|----------|----------|---------------|
| **S5** (ORB) | `S5: ORB-low break but bull regime — short disarmed` | Price broke **below** ORB low → short signal condition met. But the S5 short-side guard requires `qqq_bear200 = True` (QQQ below 200-day SMA). Since QQQ is in a bull regime, the short is **correctly blocked**. The long side wasn't triggered (price didn't break above ORB high). |

### The Order Placement Code Path (That Was Never Reached)

When a signal fires, the call chain is:

```
run_s1() → broker.place_order_safe("QQQ", shares, "buy", "S1", sl=..., tp=...)
         → Broker.place_order_safe()  [broker.py]
           → self.place_order(symbol, qty, side, tag, sl=sl, tp=tp)
           → AlpacaBroker.place_order(symbol, qty, side, tag)  [TypeError fallback]
           → self._trade.submit_order(MarketOrderRequest(...))
           → Alpaca API (paper)
```

In `live_trader.py`, S1 signal placement code:

```python
if signal_cond[recent.index].any():
    price = float(data["Close"].iloc[-1])
    ...
    shares = (equity * RISK_S1 * vix_mult * broker.RISK_SCALE) / (price * STOP_S1)
    logger.info(f"S1 SIGNAL QQQ sweep_low price={price:.2f} shares={shares:.1f}")
    broker.place_order_safe("QQQ", shares, "buy", "S1",
                            sl=price*(1-STOP_S1), tp=price*(1+STOP_S1*RR_S1))
```

This code was **never reached** because `signal_cond[recent.index].any()` was always `False` during the live sessions.

### Root Cause: No Signal = No Order

The strategies are **signal-gated**. Every strategy has at minimum:

1. A **market structure filter** (sweep, FVG, ORB breakout, momentum rank, volume threshold)
2. A **regime filter** (VIX level, SPY golden cross, QQQ vs 200d SMA, trend EMAs)
3. A **position check** (`if sym in open_syms: skip`)
4. Optional **GEX filter** (S1/S4 require negative gamma exposure)

During the 2 live sessions, the market conditions did not produce any signal that passed all filters. **This is the expected behavior of a well-designed trading system** — it only trades when its edge is present.

---

## Question 3: Were Dry-Run Flags Enabled by Default?

**No.** The `--dry-run` flag defaults to `False` (disabled). Running without `--dry-run` produces live (real paper) orders.

```python
parser.add_argument("--dry-run", action="store_true",
                    help="Print intended orders without placing them")
args = parser.parse_args()
# args.dry_run is False unless --dry-run was explicitly passed
```

However, **19 of 21 sessions were explicitly run with `--dry-run`** on the command line. The evidence is in every START log line:

```
2026-06-28 01:10:56,820 INFO START session=asian broker=alpaca dry_run=True
2026-06-28 09:24:33,668 INFO START session=asian broker=alpaca dry_run=True
...  (17 more dry-run sessions)
2026-06-28 21:31:46,960 INFO START session=all broker=alpaca dry_run=False
2026-07-02 19:39:21,448 INFO START session=orb broker=alpaca dry_run=False
```

### Where Dry-Run IS and IS NOT Specified

| Runner | Command | `--dry-run`? |
|--------|---------|:------------:|
| `run.sh` (Alpaca) | `python3 live_trader.py --broker alpaca --session "$SESSION"` | ❌ **LIVE** |
| `run.sh` (Binance BTC) | `python3 live_trader.py --broker binance --session btc --dry-run` | ✅ Dry-run |
| `main.yml` (Alpaca all) | `python live_trader.py --broker alpaca --session all` | ❌ **LIVE** |
| `main.yml` (Overnight) | `python live_trader.py --broker alpaca --session overnight` | ❌ **LIVE** |
| `main.yml` (BTC) | `python live_trader.py --broker binance --session btc --dry-run` | ✅ Dry-run |
| `paper-trade.yml` | `python live_trader.py --broker alpaca --session all` | ❌ **LIVE** |
| `schedule_mt5.ps1` (all tasks) | `python live_trader.py --broker mt5 --session $session` | ❌ **LIVE** |

**Key finding:** The automation scripts (`run.sh`, `main.yml`, `paper-trade.yml`, `schedule_mt5.ps1`) run Alpaca **without** `--dry-run`. If these scripts had actually executed successfully, they would have placed real paper orders (subject to signal availability). The 19 dry-run sessions were all **manual invocations** with `--dry-run` added by the operator.

---

## Question 4: Were Broker/Session Arguments Wrong?

### Broker Arguments Were Correct

All sessions used valid broker names (`alpaca`, `binance`). The Alpaca broker successfully connected and returned account equity:

```
2026-06-28 21:31:48,107 INFO DD-throttle: peak=$100,000 ...  ← equity fetched from Alpaca
2026-07-02 19:39:23,061 INFO DD-throttle: peak=$100,000 dd=-1.5% ...
```

### Session Arguments Were Sometimes Suboptimal

| Issue | Evidence | Impact |
|-------|----------|--------|
| **Saturday live run** (`session=all` on 2026-06-28, a Saturday) | Log: `S5: opening-range (9:00 ET) bar not formed yet` | Weekend data is static. All strategies see Friday's close replicated. No new signals can form. **Wasted a live session on closed markets.** |
| **`session=all` runs S5 even outside ORB hours** | `session=all` calls `run_s5()` unconditionally, but S5 self-gates with "opening-range bar not formed yet" | Harmless (strategy self-gates), but wastes API calls and log lines. |
| **`session=all` runs S3 outside EOD hours** | S3 uses `yfinance` daily data (not intraday), so it can fire at any time | Not harmful, but can produce signals outside intended EOD window. |

### State File Contamination Bug

Early sessions mixed default-path and per-broker-path state files, producing nonsensical readings:

```
2026-06-28 21:31:48,107 INFO DD-throttle: peak=$100,000 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +300.0%
2026-06-29 15:36:27,176 INFO DD-throttle: peak=$25,000 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +2500000.0%
```

**Code in `live_trader.py`:**

```python
def update_risk_state(equity, broker_name="default"):
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "logs", f"risk_state_{broker_name}.json")
```

The function writes to `risk_state_{broker_name}.json`, but the old default `risk_state.json` still exists with stale June data:

```json
// risk_state.json (stale)
{"month_key": "2026-06", "month_start_equity": 100000.0, "peak_equity": 100000.0}

// risk_state_alpaca.json (current)
{"month_key": "2026-07", "month_start_equity": 98432.63, "peak_equity": 100000.0}
```

The +300% reading happened because `month_start_equity` was $25,000 (written by an earlier Binance session that used the default path), and equity was $100,000 (Alpaca) → `($100k - $25k) / $25k = 300%`.

**Impact:** Could trigger false monthly kill-switch if the contamination produced a sufficiently negative reading. In this case it was positive, so no harm — but it's a latent bug.

### Missing `[risk]` Section in `config.ini`

The active `config.ini` has **no `[risk]` section**. All risk parameters fall back to code defaults:

```python
_risk_cfg      = load_config("risk")               # empty dict
DAILY_KILL_PCT = float(_risk_cfg.get("daily_loss_limit", "0.05"))    # = 0.05
TARGET_DD      = float(_risk_cfg.get("target_drawdown", "0.08"))     # = 0.08
MONTHLY_KILL_PCT = float(_risk_cfg.get("monthly_loss_limit", "0.04")) # = 0.04
daily_start_equity = float(_risk_cfg.get("session_start_equity", str(equity)))
```

Since `session_start_equity` is absent, it defaults to the **current equity** at startup, making the daily kill-switch permanently ineffective (`daily_pnl_pct = 0.0%` → never triggers -5%).

### Binance $0 Equity Bug

```
2026-06-28 23:52:47,005 INFO DD-throttle: peak=$0 dd=+0.0% throttle=1.00 -> RISK_SCALE=1.00 | month P&L +0.0%
```

Binance API returned $0 equity (unfunded demo). This was persisted as `peak_equity=0` to `risk_state_binance.json`. The `max(peak, 1)` guard prevents division-by-zero, but produces nonsensical throttle values.

---

## Question 5: Were Filters Blocking All Strategies?

### Filters Are Working Correctly — They Found No Edge

The system has 11 strategy/filter combinations. During the 2 live sessions, here is what each filter did:

#### Live Session #1 (`session=all`, Saturday 2026-06-28)

| Strategy | Filter(s) Applied | Result | Verdict |
|----------|-------------------|--------|---------|
| **S1** | Asian-low sweep + VWAP reclaim + EMA50 + GEX negative | `close=706.00 asian_low=705.31` — close above Asian low, no sweep | ✅ Correct |
| **S2** | FVG + strong candle + sweep + London window + EMA50 | `S2 no signal` — no FVG+sweep combo in London hours | ✅ Correct |
| **S4** | Same as S1 + SPY bull + EMA50>EMA200 trend + GEX neg | `no signal` for both QQQ and SPY | ✅ Correct |
| **S5** | ORB 9:00 ET bar + breakout window 10-13 ET + volume | `opening-range (9:00 ET) bar not formed yet` — Saturday, no bar | ✅ Correct (but shouldn't have been run on a weekend) |
| **S3** | Volume z-score >1.5 + daily return >1% + VIX>0 | Best: GDX abnvol=0.67σ (needs >1.5σ) | ✅ Correct |

#### Live Session #2 (`session=orb`, Thursday 2026-07-02)

| Strategy | Filter(s) Applied | Result | Verdict |
|----------|-------------------|--------|---------|
| **S5 long** | Price > ORB high + SPY bull + volume >0.6× OR vol | Price was below ORB low, not above ORB high | ✅ No long signal |
| **S5 short** | Price < ORB low + QQQ < 200d SMA + volume | `ORB-low break but bull regime — short disarmed` | ✅ **Correctly blocked** counter-trend short |

### GEX Filter Activity

The GEX (Gamma Exposure) filter was active and correctly applied:

- **2026-06-28 (negative GEX, allows trades):** `GEX QQQ: net=-2.31B` → `neg_gex = True` → sweep trades would have been allowed if sweeps had fired.
- **2026-06-29 (positive GEX, blocks trades):** `GEX QQQ: net=0.80B` → if a sweep had fired, it would have been blocked with `GEX POSITIVE ($0.8B) - dealers pin price. Skipping.`
- **2026-07-02:** `GEX QQQ: net=-2.10B` → negative, would have allowed trades.

### VIX Regime Filter

VIX was consistently low (17.7–18.0), setting `vix_mult=1.0` (full risk). No strategy was paused by VIX:

```
2026-06-28: vix_ma21=17.8 vix_mult=1.0
2026-07-02: vix_ma21=18.0 vix_mult=1.0
```

The VIX gate only activates at VIX≥20 (0.5× risk) or VIX>25 (pause all). This never happened.

### Conclusion: Filters Did NOT Over-Block

No filter incorrectly blocked a valid signal. The market conditions during the 2 live sessions simply did not produce any strategy edges:

- No Asian-low sweeps occurred
- No FVG+sweep patterns in London gold
- No ORB breakouts in the correct direction (long breakout would have needed price > ORB high; short was correctly blocked by bull regime)
- No abnormal volume spikes

---

## Question 6: Was Order Placement Disabled?

**No.** Order placement was fully functional during the 2 live sessions.

### Evidence: Code Path Verification

When `dry_run=False`, the broker chain is:

```python
# live_trader.py — main block
broker = make_broker(args.broker)      # → AlpacaBroker() with real API client
if args.dry_run:                        # False — skip wrapper
    broker = DryRunBroker(broker)
```

The `AlpacaBroker.place_order` method submits real orders to the Alpaca paper API:

```python
# alpaca_broker.py
def place_order(self, symbol: str, qty: float, side: str, tag: str):
    if qty < 1:
        print(f"  {tag} {symbol}: qty < 1, skip")
        return None
    order = self._trade.submit_order(MarketOrderRequest(
        symbol=symbol,
        qty=int(qty),
        side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    print(f"  {tag} {symbol}: {side.upper()} {int(qty)} shares | {order.id}")
    return order
```

And `Broker.place_order_safe` (the wrapper called by strategies) has retry logic:

```python
# broker.py
def place_order_safe(self, symbol, qty, side, tag, max_retries=3, sl=None, tp=None):
    for attempt in range(max_retries):
        try:
            result = self.place_order(symbol, qty, side, tag, sl=sl, tp=tp)
            logger.info(f"FILL {tag} {side.upper()} {qty:.1f} {symbol}{brk}")
            alerts.send(f"FILL {tag} {side.upper()} {qty:.1f} {symbol}{brk}")
            return result
        except Exception as e:
            ...
```

**Note:** `AlpacaBroker.place_order` does not accept `sl`/`tp` keyword arguments. The `place_order_safe` wrapper handles this via a `TypeError` fallback:

```python
try:
    result = self.place_order(symbol, qty, side, tag, sl=sl, tp=tp)
except TypeError:
    result = self.place_order(symbol, qty, side, tag)   # ← falls back here
```

This means **stop-loss and take-profit brackets are NOT attached** on Alpaca orders. The SL/TP values are logged but never sent to the broker. This is a **safety gap** (orders go out "naked" without broker-side stops), but it does not prevent order placement.

### What WOULD Have Happened If a Signal Fired

If S1 had found a sweep signal during the live Saturday session:

1. `logger.info("S1 SIGNAL QQQ sweep_low price=706.00 shares=...")` — logged
2. `broker.place_order_safe("QQQ", shares, "buy", "S1", sl=695.59, tp=737.08)` — called
3. `Broker.place_order_safe` calls `AlpacaBroker.place_order("QQQ", shares, "buy", "S1")`
4. `self._trade.submit_order(MarketOrderRequest(...))` — submitted to Alpaca paper API
5. `logger.info("FILL S1 BUY X.X QQQ SL=695.59 TP=737.08")` — logged
6. `alerts.send("FILL S1 BUY X.X QQQ SL=695.59 TP=737.08")` — Telegram alert sent

The order placement pipeline is **functional**. It was simply never triggered.

---

## Question 7: What Exact Command Runs Live Trading Safely?

### For Paper Trading (Alpaca Paper Account)

```bash
# Run a specific session LIVE (paper):
python3 live_trader.py --broker alpaca --session asian
python3 live_trader.py --broker alpaca --session orb
python3 live_trader.py --broker alpaca --session eod
python3 live_trader.py --broker alpaca --session all

# For overnight drift:
python3 live_trader.py --broker alpaca --session overnight

# For monthly momentum rebalance:
python3 live_trader.py --broker alpaca --session rebal
```

**Omit `--dry-run`** to place real orders on the Alpaca paper account.

### For Dry-Run (Simulation)

```bash
# Add --dry-run to simulate without placing orders:
python3 live_trader.py --broker alpaca --session asian --dry-run
```

### For MT5 (Prop Account via Windows VPS)

```powershell
# On the Windows VPS with MT5 terminal open:
python live_trader.py --broker mt5 --session all
python live_trader.py --broker mt5 --session overnight
```

### Safe Transition Checklist Before Going Live

```bash
# 1. Verify dry-run produces signals:
python3 live_trader.py --broker alpaca --session all --dry-run

# 2. Verify Alpaca paper account is funded and API is connected:
python3 -c "from alpaca_broker import AlpacaBroker; b=AlpacaBroker(); print(f'Equity: \${b.get_account():,.2f}')"

# 3. Run a single session LIVE on paper:
python3 live_trader.py --broker alpaca --session asian

# 4. Check logs/trader.log for FILL lines:
grep "FILL" logs/trader.log

# 5. Only after confirming paper fills work, schedule via cron/GH Actions.
```

---

## Question 8: What Checks Must Pass Before Enabling Live Trading?

### Pre-Live Gate Tree

The following is the complete chain of checks that must ALL pass for a real order to reach the broker:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. COMMAND LINE                                              │
│    --dry-run must NOT be passed                              │
│    --broker must be valid (alpaca, mt5, ctrader, binance)    │
│    --session must be valid and appropriate for the time      │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. BROKER INITIALIZATION                                     │
│    Credentials in config.ini or env vars must be valid       │
│    AlpacaBroker.__init__ → TradingClient(paper=True)        │
│    If credentials start with "YOUR_" → NotConfiguredError   │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ACCOUNT & EQUITY                                          │
│    broker.get_account() must return > 0                      │
│    (Binance returned $0 → state corruption)                 │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. DD-THROTTLE                                               │
│    update_risk_state() computes drawdown from peak equity    │
│    throttle = max(0.3, min(1.0, (0.08 + cur_dd) / 0.08))   │
│    broker.RISK_SCALE *= throttle                             │
│    If DD exceeds 8%, throttle drops to 0.3 (30% sizing)     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. MONTHLY KILL SWITCH                                       │
│    If month_pnl <= -4% → CRITICAL log, sys.exit(0)          │
│    "No new orders until next month"                          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. DAILY KILL SWITCH                                         │
│    If daily_pnl <= -5% → CRITICAL log, sys.exit(0)          │
│    NOTE: Currently ineffective — session_start_equity        │
│    defaults to current equity, making daily_pnl = 0% always  │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. REGIME FILTER                                             │
│    VIX 21d MA computed from yfinance                         │
│    vix_mult: 1.0 (VIX<20), 0.5 (20≤VIX<25), 0.0 (VIX≥25)   │
│    If vix_mult == 0 → all strategies PAUSED                  │
│    spy_bull: SPY EMA50 > EMA200 (golden/death cross)        │
│    qqq_bear200: QQQ < 200d SMA (for S5 short arm)           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. STRATEGY-SPECIFIC FILTERS                                 │
│    Each strategy has its own gates (see below)               │
│    All must produce a SIGNAL for order placement             │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. POSITION CHECK                                            │
│    if sym in open_syms: skip                                 │
│    (prevents doubling up on existing positions)              │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. ORDER PLACEMENT                                          │
│     broker.place_order_safe(symbol, qty, side, tag, sl, tp) │
│     → MarketOrderRequest submitted to Alpaca                 │
│     → Retry up to 3× on failure                             │
│     → Log "FILL", send Telegram/email alert                  │
└─────────────────────────────────────────────────────────────┘
```

### Strategy-Specific Filter Details

| Strategy | Filter Chain | Signal Condition |
|----------|-------------|------------------|
| **S1** (Asian Sweep) | `vix_mult > 0` → not in position → Asian-low sweep (`Low < AsianLow` AND `Close > AsianLow`) → in session window → `Close > VWAP` → `Close > DailyEMA50` → not high-vol → GEX negative | All conditions true in last 3 bars |
| **S2** (Gold FVG) | `vix_mult > 0` → not in position → sweep active → in London window → strong candle → FVG present → EMA50 trend | All conditions true in last 4 bars |
| **S3** (Abn. Vol) | `vix_mult > 0` → not in position → `abnvol > 1.5` → `dayret > 1%` | Yesterday's bar qualifies |
| **S4** (Multi-Sweep) | `spy_bull=True` → `vix_mult > 0` → sweep → in session → EMA50 > EMA200 → not high-vol → GEX negative | All conditions true in last 3 bars |
| **S5** (ORB) | `VIX < 20` → not in position → 9:00 ET bar exists → bars in 10-13 ET window → **Long:** `price > ORB_high` AND `spy_bull` AND `vol_ok` / **Short:** `price < ORB_low` AND `qqq_bear200` AND `vol_ok` | Breakout confirmed |
| **BTC** (Sweep) | In 08-16 UTC window → daily EMA50 > EMA200 (uptrend) → Asian-low sweep + reclaim | All conditions true |
| **XSMOM** | ≥4 symbols with ≥260 daily bars → top-3 by 12-1 month momentum → not already at target weight | Monthly rebalance signal |
| **OVN** | Not held → Mon/Tue 15:00-16:00 ET close window → qty > 0 | Weekday + time window |
| **BTC-TREND** | Donchian 20 breakout → vol-target sizing → delta > tolerance | Trend change or vol shift |
| **SWEEP-BASKET** | `vix_mult > 0` → sweep signal on basket symbol (same as S1) | Any basket symbol fires |

### Critical Observation

During the 2 live sessions, the system reached **step 8** (strategy filters) and stopped there. No strategy produced a signal that passed all its conditions. The system was operating correctly — it just didn't find any tradeable edges during those specific market moments.

---

## Summary: The Three Layers of Root Cause

| Layer | Cause | Impact | Fix |
|-------|-------|--------|-----|
| **Layer 1 (Primary)** | 90% of sessions ran with `--dry-run`, wrapping the broker in `DryRunBroker` which intercepts all orders | Only 2 live attempts in 5 days | Remove `--dry-run` from production commands; reserve it for testing only |
| **Layer 2 (Secondary)** | The 2 live sessions encountered no strategy signals (no sweeps, no FVG, no valid ORB breakout direction, weekend stale data) | Zero orders possible even with live broker | Run live sessions during **market hours on weekdays only**; increase scheduling frequency |
| **Layer 3 (Tertiary)** | Scheduling/config gaps: weekend runs, missing `[risk]` section, state file contamination, CSV mapping bug, Alpaca SL/TP not attached | Reduced reliability but didn't directly prevent orders | Fix per recommendations below |

---

## Recommended Fixes (Prioritized)

### P0 — Critical (Blocks Live Trading)

1. **Add weekend guard:** Skip sessions on Saturday/Sunday unless crypto. Code:
   ```python
   if now_et().weekday() >= 5 and args.session not in ("btc", "btctrend"):
       logger.info("Market closed (weekend) - skip")
       sys.exit(0)
   ```
   The live Saturday session (#1) was entirely wasted.

2. **Run more live sessions during weekday market hours.** 2 live attempts in 5 days is insufficient. The GitHub Actions cron schedules (`main.yml`) are correct for this but may not have been executing.

3. **Verify GitHub Actions actually run.** Check the Actions tab on the repo for green checkmarks. The local `trader.log` only captures local Mac runs — GH Actions logs are ephemeral unless the workflow uploads them as artifacts.

### P1 — High (Safety Gaps)

4. **Add `[risk]` section to `config.ini`** (copy from `config.example.ini`). Without it, `session_start_equity` defaults to current equity, making the daily kill-switch permanently inert.

5. **Fix Alpaca SL/TP attachment.** `AlpacaBroker.place_order()` doesn't accept `sl`/`tp` params. The `TypeError` fallback in `place_order_safe` silently drops the brackets. All Alpaca orders go out **naked** (no broker-side stop-loss). Fix: add `sl`/`tp` to the `place_order` signature and submit as a bracket order via Alpaca's API.

6. **Clean up stale `risk_state.json`.** The default-path file has June data while per-broker files have July data. Delete it or add a migration guard.

### P2 — Medium (Reliability)

7. **Fix CSV fallback timeframe mapping** in `broker.py`:
   ```python
   # Current (broken): "1Day" → "1min"
   tf_tag = "hourly" if tf == "1Hour" else "1min"
   
   # Fixed:
   tf_tag = {"1Hour": "hourly", "1Day": "daily", "1Min": "1min"}.get(tf, "1min")
   ```

8. **Guard against $0 equity.** In `update_risk_state()`, refuse to write state if equity ≤ 0:
   ```python
   if equity <= 0:
       logger.error(f"Invalid equity ${equity} from {broker_name}; skipping state update")
       return 1.0, 0, 0, 0
   ```

9. **Add session deduplication.** Three identical sessions started within 51 seconds on 2026-06-28. Add a lock file or cooldown timer.

### P3 — Low (Quality of Life)

10. **Add `(LIVE)` / `(DRY)` prefix** to all log lines for instant mode identification.
11. **Write JSONL trade log** (`logs/trades.jsonl`) for automated analysis.
12. **Add structured health-check** (`logs/heartbeat.json`) with last-run timestamp.

---

*End of Root Cause Analysis*
