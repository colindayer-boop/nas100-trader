# LIVE EXECUTION FLOW — nas100-trader

> Trace from signal generation through risk checks, position sizing, broker
> execution, and logging. Every step the system takes for a single trade.

---

## Overview

```
Scheduler fires
       │
       ▼
┌───────────────────┐
│  live_trader.py   │  ← entrypoint
│  (main block)     │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  1. BROKER INIT   │  make_broker(name) → may wrap in DryRunBroker
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  2. ACCOUNT FETCH │  broker.get_account() → equity
│     + POSITIONS   │  broker.get_positions() → open_syms dict
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  3. REGIME DETECT │  get_regime() → VIX, SPY trend, QQQ 200d
│     + GEX         │  get_gex_levels() → gamma flip, walls
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  4. RISK ENGINE   │  update_risk_state() → DD-throttle scale
│     DD-throttle   │  monthly kill-switch check
│     kill-switches │  daily kill-switch check
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  5. SESSION       │  args.session → {asian, orb, eod, all,
│     DISPATCH      │     btc, rebal, overnight, btctrend, sweep}
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  6. STRATEGY      │  run_s1 / run_s2 / ... / run_sweep_basket
│     EVALUATION    │  → SIGNAL or "no signal"
└───────┬───────────┘
        │
        ▼  (on signal)
┌───────────────────┐
│  7. POSITION      │  shares = (equity * RISK * vix_mult *
│     SIZING        │    RISK_SCALE) / (price * STOP)
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  8. ORDER         │  broker.place_order_safe(symbol, qty, side,
│     EXECUTION     │    tag, sl=..., tp=...)
│                    │  → retries with exponential backoff
│                    │  → broker-side SL/TP attached
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  9. ALERTS +      │  alerts.send() → Telegram + Email + Console
│     LOGGING       │  logger.info() → logs/trader.log (rotating)
│                    │  state file update (BTC/overnight only)
└───────────────────┘
```

---

## Detailed Step-by-Step: A Single Trade

### Step 0 — Scheduler fires

Three scheduling paths exist:

**GitHub Actions (Alpaca cloud paper):**
```
.github/workflows/main.yml
  cron "30 7 * * 1-5"   → 07:30 UTC → session "all" (Asian window)
  cron "30 14 * * 1-5"  → 14:30 UTC → session "all" (ORB window)
  cron "0 21 * * 1-5"   → 21:00 UTC → session "all" (EOD window)
  cron "55 19 * * 1,2"  → 19:55 UTC → session "overnight" (enter)
  cron "0 14 * * 2,3"   → 14:00 UTC → session "overnight" (exit)
```
Each cron triggers: `python live_trader.py --broker alpaca --session <X>`

**Windows Task Scheduler (VPS / MT5):**
```
schedule_mt5.ps1 registers:
  Nas100Bot-MT5       → hourly   → --session all
  Nas100Bot-Overnight → 30 min   → --session overnight
  Nas100Bot-BTC       → hourly   → --session btc
  Nas100Bot-BTCTrend  → daily    → --session btctrend
  Nas100Bot-Rebal     → daily    → --session rebal (1st of month only)
```
Strategies self-gate by ET clock, so frequent triggers are safe.

**Local:**
```
./run.sh [session]   →  python3 live_trader.py --broker alpaca --session "$1"
```

---

### Step 1 — Broker initialization

```python
# live_trader.py main block
broker = make_broker(args.broker)     # e.g. AlpacaBroker()
if args.dry_run:
    broker = DryRunBroker(broker)     # wraps: intercepts place_order
```

`make_broker()` dispatches to the right adapter. Each adapter reads credentials from `config.ini` via `load_config()`, with env-var overlay (env wins). If credentials are placeholder, raises `NotConfiguredError`.

**DryRunBroker** wraps any broker: `get_bars` falls back to local CSV, `get_account` returns $25k default if auth fails, `place_order` prints instead of executing.

---

### Step 2 — Account & position fetch

```python
equity    = broker.get_account()       # float
open_syms = broker.get_positions()     # {symbol: position_object}
```

- **Alpaca:** SDK call, returns live equity and position objects with `.qty`, `.current_price`.
- **MT5:** `mt5.account_info().balance`, `mt5.positions_get()`.
- **Binance:** Signed REST `/v3/account`.
- **DryRun:** Catches auth errors, returns $25,000 / empty dict.

---

### Step 3 — Regime detection

```python
vix_ma21, spy_bull, vix_mult, qqq_bear200 = get_regime()
```

`get_regime()` downloads:
- **VIX** (60 days daily) → 21-day moving average
- **SPY** (500 days daily) → EMA50 vs EMA200 (Golden/Death cross)
- **QQQ** (400 days daily) → price vs 200-day SMA

Produces a risk multiplier:
| VIX 21d MA | vix_mult | Effect |
|------------|----------|--------|
| < 20 | 1.0 | Full size |
| 20–25 | 0.5 | Half size |
| > 25 | 0.0 | **No new trades** |

`get_gex_levels(broker, symbol)` optionally computes gamma exposure from live options chain (via yfinance), producing: net GEX, gamma flip, put wall, call wall. Used as a **signal filter** in S1/S4 (skip if GEX positive — dealers pin price).

---

### Step 4 — Risk engine

#### 4a. DD-throttle (conformal)

```python
_throttle, _cur_dd, _peak, _month_pnl = update_risk_state(equity, broker_name)
broker.RISK_SCALE *= _throttle
```

**State file:** `logs/risk_state_{broker}.json`

Algorithm:
1. Load peak equity and month-start equity from JSON state.
2. Update peak = max(historical peak, current equity).
3. Compute drawdown = (equity - peak) / peak (always ≤ 0).
4. Throttle = clamp((TARGET_DD + dd) / TARGET_DD, 0.3, 1.0).
   - TARGET_DD defaults to 8% (from `config.ini [risk] target_drawdown`).
   - At 0% drawdown: throttle = 1.0 (full size).
   - At -4% drawdown: throttle = 0.5 (half size).
   - At -8% drawdown: throttle = 0.0... clamped to 0.3 (floor).
5. On new calendar month: reset month_start_equity.
6. Persist state JSON.

**Effect:** `broker.RISK_SCALE` is multiplied by the throttle. All subsequent position sizing uses the reduced RISK_SCALE.

#### 4b. Monthly kill-switch

```python
if _month_pnl <= -MONTHLY_KILL_PCT:   # default 4%
    sys.exit(0)   # halt — no new orders until next month
```

Alerts via Telegram + email before exiting.

#### 4c. Daily kill-switch

```python
daily_pnl_pct = (equity - daily_start_equity) / daily_start_equity
if daily_pnl_pct <= -DAILY_KILL_PCT:  # default 5%
    sys.exit(0)
```

---

### Step 5 — Session dispatch

```python
if args.session == "asian":
    run_s1(broker, equity, open_syms, vix_ma21, spy_bull, vix_mult)
    run_s2(broker, equity, open_syms, vix_mult)
    run_s4(broker, equity, open_syms, spy_bull, vix_mult)
elif args.session == "orb":
    run_s5(broker, equity, open_syms, vix_ma21, spy_bull, qqq_bear200)
elif args.session == "all":
    run_s1(); run_s2(); run_s4(); run_s5(); run_s3(); run_sweep_basket()
# ... etc
```

Each strategy function is self-contained: it fetches its own bars, checks its own gates (position exists, VIX regime, session window), and either fires `place_order_safe()` or logs "no signal".

---

### Step 6 — Strategy evaluation (example: S1 Asian Sweep)

```
S1 SIGNAL PATH:

1. Gate: "QQQ" in open_syms?  → SKIP (already in position)
2. Gate: vix_mult == 0?       → PAUSE (extreme VIX)
3. Fetch: broker.get_bars("QQQ", "1Hour", 30)
4. Compute:
   a. Asian session range (18:00–02:00 ET) → AsianHigh, AsianLow
   b. InSession window (02:00–05:00 or 09:00–12:00 ET)
   c. VWAP (cumulative typical-price × volume)
   d. Daily EMA50 (from 16:00 ET daily closes)
   e. ATR(14) vs 200-bar average → HighVol filter
5. Signal condition:
   SweepLow   = Low < AsianLow AND Close > AsianLow
   FullSignal = SweepLow AND InSession AND Close > VWAP AND
                Close > DailyEMA50 AND NOT HighVol AND AsianLow.notna()
6. GEX filter: if net_gex > 0 → SKIP (dealers pin price, breakout unlikely)
7. Check last 3 bars: if any bar satisfies FullSignal → SIGNAL
```

---

### Step 7 — Position sizing

When a signal fires, the position size is computed:

```python
shares = (equity * RISK_PCT * vix_mult * broker.RISK_SCALE) / (price * STOP_PCT)
```

**Per-strategy constants:**

| Strategy | RISK_PCT | STOP_PCT | RR | Effective Risk/Trade |
|----------|----------|----------|----|---------------------|
| S1 Asian Sweep | 0.70% | 1.5% | 3:1 | 0.70% × vix_mult × RISK_SCALE |
| S2 Gold FVG | 0.50% | 1.5% | 3:1 | 0.50% × vix_mult × RISK_SCALE |
| S3 Abnormal Vol | 0.40% | 2.0% | — | 0.40% × vix_mult × RISK_SCALE |
| S4 Multi-Sweep | 0.40% | 1.5% | 3:1 | 0.40% × vix_mult × RISK_SCALE |
| S5 ORB | 0.75% | 1.0% | 3:1 | 0.75% × RISK_SCALE |
| BTC sweep | 0.60% | 2.5% | 3:1 | 0.60% × RISK_SCALE |

**Three multipliers stack:**
1. `RISK_PCT` — strategy's base risk (validated in walk-forward).
2. `vix_mult` — regime scaler (0.0/0.5/1.0 based on VIX 21d MA).
3. `broker.RISK_SCALE` — broker-specific scale (e.g. Tradovate = 0.5) **already multiplied** by DD-throttle.

---

### Step 8 — Order execution

```python
broker.place_order_safe(symbol, qty, side, tag,
                         sl=price*(1-STOP), tp=price*(1+STOP*RR))
```

**`place_order_safe()` in `broker.py`:**

```
FOR attempt IN 1..max_retries (default 3):
    TRY:
        result = self.place_order(symbol, qty, side, tag, sl=sl, tp=tp)
        → if broker doesn't support sl/tp kwargs: fallback to plain order
        LOG: "FILL {tag} {side} {qty} {symbol} SL={sl} TP={tp}"
        ALERT: alerts.send("FILL ...")
        RETURN result
    EXCEPT:
        IF last attempt:
            LOG: "ORDER_FAIL {tag} {symbol} after N attempts"
            ALERT: alerts.send("ORDER FAIL ...")
            RETURN None
        ELSE:
            sleep(2^attempt)   → 1s, 2s, 4s
```

**Key safety properties:**
- **Broker-side SL/TP**: stop-loss and take-profit are attached at the broker level, not managed by the bot. If the VPS dies, the broker still enforces stops.
- **No double-send**: after max retries, returns `None`. Does NOT retry from the strategy level.
- **Naked order warning**: if `sl is None`, logs a warning.

**DryRunBroker** overrides: prints `[DRY-RUN] WOULD BUY/SELL {qty} {symbol} ({tag})` and sends a Telegram alert.

---

### Step 9 — State persistence (BTC/overnight only)

Strategies that hold positions across runs (BTC sweep, BTC trend, overnight) persist state to JSON:

**BTC sweep:** `logs/btc_state.json`
```json
{
  "active": true,
  "entry": 43500.0,
  "stop": 42412.5,
  "target": 46762.5,
  "qty": 0.00500
}
```

On next run, the strategy checks:
1. Is state.active AND is BTC in open_syms? → continue holding.
2. Is state.active but BTC NOT in open_syms? → broker SL/TP closed it. Clear state. Do NOT open new position.
3. Price hit stop/target? → send sell order, clear state.

**Overnight:** `logs/ovn_state.json` — similar pattern.

**BTC trend:** `logs/btc_trend_state.json` — tracks target qty for rebalancing.

---

### Step 10 — Logging

```
logs/trader.log
  Format: "%(asctime)s %(levelname)s %(message)s"
  Handler: RotatingFileHandler(maxBytes=5MB, backupCount=5)
  Also: StreamHandler(sys.stdout)
```

**Log patterns consumed by monitoring tools:**

| Pattern | Example | Consumed by |
|---------|---------|-------------|
| `START session={X}` | `START session=asian broker=alpaca` | check_health, dashboard |
| `SESSION S1 start` | `SESSION S1 start` | check_health |
| `S1 SIGNAL QQQ ...` | `S1 SIGNAL QQQ sweep_low price=385.50 shares=45.2` | check_health, dashboard |
| `FILL {tag} {side} {qty} {symbol}` | `FILL S1 BUY 45.2 QQQ SL=379.72 TP=401.33` | dashboard |
| `[DRY-RUN] WOULD ...` | `[DRY-RUN] WOULD BUY 45.2 QQQ (S1)` | dashboard |
| `ORDER_FAIL {tag}` | `ORDER_FAIL S1 QQQ after 3 attempts` | dashboard |
| `REGIME vix_ma21=...` | `REGIME vix_ma21=18.5 spy_bull=True ...` | check_health |
| `DD-throttle: ...` | `DD-throttle: peak=$25,000 dd=0.0% throttle=1.00` | dashboard |
| `END session={X}` | `END session=asian` | dashboard |

---

### Step 11 — Alerts

`alerts.send(msg)` dispatches to:

1. **Telegram** (primary): POST to `api.telegram.org/bot{token}/sendMessage`
   - Token/chat_id from `config.ini [alerts]` or env vars `ALERTS_TELEGRAM_TOKEN` / `ALERTS_CHAT_ID`.
   - Skips if token missing or starts with "YOUR_".
   - 10-second timeout.

2. **Email** (secondary): SMTP with STARTTLS.
   - Config from `[alerts]` section.
   - Skips if any field missing.

3. **Console** (always): `print(f"[ALERT] {msg}")`

**Alert events:**
- FILL — order filled (from `place_order_safe`)
- ORDER FAIL — order failed after retries (from `place_order_safe`)
- DRY RUN — simulated fill (from `DryRunBroker`)
- KILL SWITCH — daily or monthly loss limit hit (from `live_trader.py`)
- MONTHLY KILL — month-to-date loss limit hit
- S5 WATCHDOG — opening-range bar missing (from `s5_watchdog.py`)
- Daily heartbeat — once-daily OK ping at 17:xx ET

---

## Complete Example: S1 Signal → Fill

```
14:30 UTC (10:30 ET) — GitHub Actions fires main.yml cron

→ python live_trader.py --broker alpaca --session all

→ Broker init: AlpacaBroker()
  → reads config.ini [alpaca] → key/secret from env vars
  → TradingClient(key, secret, paper=True)

→ equity = broker.get_account()          → $25,432.10
→ open_syms = broker.get_positions()     → {} (no open positions)

→ get_regime()
  → yfinance: VIX 21d MA = 17.2 → vix_mult = 1.0
  → SPY EMA50 > EMA200 → spy_bull = True
  → QQQ > 200d SMA → qqq_bear200 = False

→ update_risk_state(25432.10, "alpaca")
  → peak = 25432.10, dd = 0.0%, throttle = 1.0
  → broker.RISK_SCALE = 1.0 × 1.0 = 1.0
  → month_pnl = 0.0% → no kill-switch

→ run_s1(broker, 25432.10, {}, 17.2, True, 1.0)
  → "QQQ" not in open_syms → continue
  → vix_mult = 1.0 → continue
  → broker.get_bars("QQQ", "1Hour", 30)
  → Asian range computed from 18:00–02:00 ET bars
  → SweepLow detected: bar Low < AsianLow, Close > AsianLow
  → VWAP confirmed: Close > VWAP
  → EMA50 confirmed: Close > DailyEMA50
  → Volatility OK: ATR < 1.5× ATR_200
  → GEX computed: net_gex = -$2.1B → negative → dealers will not pin → OK

  → SIGNAL: S1 QQQ sweep
  → Sizing: shares = (25432.10 × 0.007 × 1.0 × 1.0) / (385.50 × 0.015) = 30.8 shares

  → broker.place_order_safe("QQQ", 30.8, "buy", "S1",
      sl=379.72, tp=401.33)
    → Attempt 1: AlpacaBroker.place_order() → market buy 30.8 QQQ
    → Result: filled at $385.52
    → LOG: "FILL S1 BUY 30.8 QQQ SL=379.72 TP=401.33"
    → ALERT: Telegram → "FILL S1 BUY 30.8 QQQ SL=379.72 TP=401.33"
    → RETURN order_id

→ run_s2(...) → "No signal"
→ run_s4(...) → "No signal"
→ run_s5(...) → "VIX < 20, checking ORB" → "No valid breakout"
→ run_s3(...) → "No signal"
→ run_sweep_basket(...) → "SPY: no signal", "IWM: no signal", ...

→ LOG: "END session=all"
→ 17:xx ET check: no (it's 10:30 ET) → logger.info only, no heartbeat alert
```

---

## Risk Layers Summary

```
Layer 1: REGIME GATE (VIX)
  ├─ vix_mult = 0.0 → all strategies paused (extreme VIX)
  ├─ vix_mult = 0.5 → position size halved (elevated VIX)
  └─ vix_mult = 1.0 → normal

Layer 2: GEX FILTER (S1/S4 only)
  └─ net_gex > 0 → skip signal (dealers pin price, breakout fails)

Layer 3: STRUCTURAL FILTERS
  ├─ spy_bull required (S4, S5 long)
  ├─ qqq_bear200 required (S5 short)
  ├─ uptrend required (BTC sweep/trend: EMA50 > EMA200)
  ├─ HighVol filter (ATR > 1.5× mean → skip)
  └─ Already-in-position skip

Layer 4: DD-THROTTLE (conformal)
  └─ broker.RISK_SCALE *= clamp((8% + dd) / 8%, 0.3, 1.0)

Layer 5: KILL-SWITCHES
  ├─ Daily loss > 5% → sys.exit(0)
  └─ Monthly loss > 4% → sys.exit(0)

Layer 6: BROKER-SIDE STOPS
  └─ SL/TP attached at broker level → enforced even if bot offline
```

Each layer is independent and composable. A trade must pass ALL layers to execute.
