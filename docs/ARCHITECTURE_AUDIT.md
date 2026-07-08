# ARCHITECTURE AUDIT — nas100-trader

> Read-only audit. No code was modified.

---

## 1. System Overview

`nas100-trader` is a multi-strategy, multi-broker algorithmic trading system. It evolved from a single-strategy OANDA paper trader into a production system running 9 strategy pillars across 5 broker adapters, deployed simultaneously on a Windows VPS (MT5/Pepperstone), GitHub Actions (Alpaca cloud paper), and locally (Mac).

The architecture is **monolithic by design**: a single 964-line `live_trader.py` contains all strategies, the regime detection layer, the risk engine, and the session dispatcher. Broker adapters are pluggable via an abstract base class. Alerts, logging, and state persistence are handled at the module level.

---

## 2. Component Map

```
                    ┌─────────────────────────────────────────────┐
                    │              SCHEDULER LAYER                 │
                    │                                             │
                    │  GitHub Actions (.github/workflows/)        │
                    │    main.yml    → 5 crons (Alpaca cloud)     │
                    │    paper-trade → 3 crons (duplicate)        │
                    │    weekly-report.yml → Fri 22:00 UTC        │
                    │                                             │
                    │  Windows Task Scheduler (VPS)               │
                    │    schedule_mt5.ps1 → 5 tasks (MT5)         │
                    │    s5_watchdog.py    → hourly canary         │
                    │                                             │
                    │  Local                                      │
                    │    run.sh → manual paper runs               │
                    └────────────────────┬────────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────────┐
                    │           live_trader.py (MAIN)              │
                    │                                             │
                    │  ┌─────────────┐  ┌──────────────────────┐  │
                    │  │  REGIME      │  │  RISK ENGINE          │  │
                    │  │  get_regime()│  │  update_risk_state()  │  │
                    │  │  get_gex()   │  │  DD-throttle          │  │
                    │  └──────┬───────┘  │  Daily kill-switch    │  │
                    │         │          │  Monthly kill-switch   │  │
                    │  ┌──────▼───────┐  └──────────┬───────────┘  │
                    │  │  STRATEGIES   │             │              │
                    │  │  S1 Asian     │  ┌──────────▼───────────┐  │
                    │  │  S2 Gold FVG  │  │  BROKER LAYER          │  │
                    │  │  S3 AbnVol    │  │  broker.py (abstract) │  │
                    │  │  S4 MultiSw   │  │  ├── AlpacaBroker     │  │
                    │  │  S5 ORB       │  │  ├── MT5Broker        │  │
                    │  │  BTC sweep    │  │  ├── BinanceBroker    │  │
                    │  │  BTC trend    │  │  ├── CTraderBroker    │  │
                    │  │  xsmom        │  │  └── TradovateBroker  │  │
                    │  │  overnight    │  │       │               │  │
                    │  │  sweep basket │  │  DryRunBroker wrapper │  │
                    │  └──────────────┘  └───────┬───────────────┘  │
                    └─────────────────────────────┼────────────────┘
                         │                         │
               ┌─────────▼──────────┐    ┌────────▼─────────┐
               │   ALERTS / LOGS    │    │   STATE FILES     │
               │   alerts.py        │    │   logs/*.json     │
               │   → Telegram       │    │   logs/trader.log │
               │   → Email          │    └──────────────────┘
               │   → Console        │
               └────────────────────┘
```

---

## 3. Dependency Graph

```
live_trader.py
├── broker.py          (Broker base, DryRunBroker, load_config)
│   └── alerts.py      (fill/error notifications)
├── alpaca_broker.py   (→ alpaca-py SDK)
├── mt5_broker.py      (→ MetaTrader5 package, Windows-only)
├── binance_broker.py  (→ requests, hmac)
├── ctrader_broker.py  (→ requests; full exec needs ctrader-open-api)
├── tradovate_broker.py(→ requests)
├── alerts.py          (→ requests for Telegram, smtplib for email)
├── yfinance           (regime: VIX, SPY, QQQ bars)
├── pandas, numpy      (signal computation)
└── scipy.stats        (GEX gamma calculation)

status.py
├── mt5_broker.py
├── broker.py (load_config)
└── alerts.py

s5_watchdog.py
├── mt5_broker.py
└── alerts.py

weekly_report.py
├── alerts.py
└── broker.py (load_config)

check_health.py
└── (standalone — reads logs/ directly)

verify_liveness.py
└── (standalone — reads CSV files directly)

dashboard/app.py
└── (standalone — reads logs/ directly, no project imports)

risk/risk_profile_loader.py
├── config/risk_profiles.yaml
└── config.ini

alpaca_paper_trader.py  [LEGACY]
└── broker.py (load_config)

paper_trade.py           [LEGACY]
└── (standalone OANDA)

conformal_overlay.py     [RESEARCH]
└── combined_3pillar.py (via exec)

macro_event_filter.py    [RESEARCH]
└── combined_3pillar.py (via exec)
```

---

## 4. Classification Summary

### PRODUCTION — In the live trading path

| Component | Status | Notes |
|-----------|--------|-------|
| `live_trader.py` | ✅ SAFE | Core trading engine. Well-structured, defensive. |
| `broker.py` | ✅ SAFE | Clean abstract interface. `place_order_safe` is robust. |
| `mt5_broker.py` | ✅ SAFE | Windows-only. Handles lot conversion, symbol mapping. |
| `alpaca_broker.py` | ✅ SAFE | Paper-first default. Clean SDK usage. |
| `binance_broker.py` | ✅ SAFE | HMAC signing correct. Public/Private endpoint split. |
| `ctrader_broker.py` | ⚠️ SCAFFOLD | Interface complete, but order execution needs WS library. Account info via REST works. |
| `tradovate_broker.py` | ⚠️ SCAFFOLD | REST auth + account works. Order execution untested live. |
| `alerts.py` | ✅ SAFE | Multi-channel with graceful degradation. |
| `status.py` | ✅ SAFE | Read-only diagnostic. |
| `s5_watchdog.py` | ✅ SAFE | Self-gating canary. Telegram alerts. |
| `weekly_report.py` | ✅ SAFE | Pulls from broker API (source of truth). |
| `risk/` package | ✅ SAFE | Profile loader with YAML + config.ini + env var cascade. |
| `dashboard/app.py` | ✅ SAFE | Pure consumer. Read-only. Never imports trading code. |

### LEGACY — Superseded but not removed

| Component | Status | Notes |
|-----------|--------|-------|
| `paper_trade.py` | 📦 LEGACY | Original OANDA trader. Standalone, no project imports. Safe to archive. |
| `paper_trade_master.py` | 📦 LEGACY | Multi-strategy paper trader predecessor. |
| `alpaca_paper_trader.py` | 📦 LEGACY | Standalone S3. Logic now in live_trader `--session eod`. |
| `Procfile` | 📦 LEGACY | Railway.app entrypoint. No longer used. |
| `.env.example` | 📦 LEGACY | OANDA env vars. No longer used. |
| `setup_vps.ps1` | 📦 LEGACY | ZIP-based VPS setup. Superseded by `setup_vps_git.ps1`. |
| `sweep_backtest.py .py` | 📦 LEGACY | Misnamed duplicate (space in filename). |
| `live_trader.py.bak` | 📦 LEGACY | Backup file. |
| `full_yearly.py.backup_*` (×4) | 📦 LEGACY | Backup variants. |
| SMA scripts (×7) | 📦 LEGACY | Abandoned SMA strategy lineage. |
| `protect_positions.py` | 📦 LEGACY | One-time MT5 cleanup. |

### RESEARCH — Validated experiments feeding into live trading

| Component | Status | Notes |
|-----------|--------|-------|
| `walkforward.py` | 🔬 RESEARCH | Core walk-forward framework. Results in FINDINGS.md. |
| `open_breakout_walkforward.py` | 🔬 RESEARCH | S5 validation (7/7 windows, Sharpe 3.21). |
| `combined_3pillar.py` | 🔬 RESEARCH | Combined P&L series. Dependency for other research. |
| `cfd_validate.py` | 🔬 RESEARCH | Validated QQQ→US100 CFD port. |
| `xsmom_proper.py` | 🔬 RESEARCH | Validated → `run_xsmom` in live_trader. |
| ~45 other backtest scripts | 🔬 RESEARCH | Various one-shot experiments. |

### DUPLICATE — Overlapping functionality

| Component | Status | Notes |
|-----------|--------|-------|
| `.github/workflows/paper-trade.yml` | ⚠️ DUPLICATE | Same cron times as `main.yml` but subset of jobs. Should be removed or merged. |
| `setup_vps.ps1` vs `setup_vps_git.ps1` | ⚠️ DUPLICATE | Old ZIP-based vs new git-based setup. |

### UNUSED — Written but never integrated

| Component | Status | Notes |
|-----------|--------|-------|
| `decay_aware_strategy_management.py` | ❓ UNUSED | 334 lines, references arXiv paper. Not wired into live_trader or backtests. Crowding/performative scores are TODO stubs. |

### DEBUG — One-time diagnostic/patch scripts

| Component | Status | Notes |
|-----------|--------|-------|
| `add_debug.py`, `debug_s5s.py`, `debug_weights*.py` | 🐛 DEBUG | One-time diagnostics. |
| `fix_s6*.py`, `fix_sma.py`, `modify_sma.py` | 🐛 DEBUG | One-time patches (S6 was dropped). |
| `patch_*.py` | 🐛 DEBUG | One-time patches. |
| `diag_live.py` | 🐛 DEBUG | Live diagnostic. |
| `final_sma_test*.py` (×4) | 🐛 DEBUG | SMA test lineage. |
| `test_*.py` (×5) | 🐛 DEBUG | Various tests. |
| `quick_check.py`, `simple_strategy_check.py` | 🐛 DEBUG | Quick checks. |

---

## 5. Architectural Strengths

1. **Broker abstraction is clean.** `Broker` base class defines 5 methods. All strategies call only these. Switching brokers is a `--broker` flag.

2. **`place_order_safe` is robust.** Retry with exponential backoff, broker-side SL/TP attachment, alert on failure. The "never double-sends" property is enforced by returning `None` after max retries.

3. **Risk engine is multi-layered.** DD-throttle (conformal) → daily kill-switch → monthly kill-switch. Per-broker state files prevent cross-account contamination.

4. **Defensive I/O everywhere.** CSV fallback for bars, JSON state files wrapped in try/except, UTF-8 stdout reconfiguration for Windows, `errors="replace"` on file reads.

5. **Observability is first-class.** `status.py`, `check_health.py`, `verify_liveness.py`, `s5_watchdog.py`, `dashboard/app.py` — five different monitoring tools covering different failure modes.

6. **Strategies self-gate by session/time.** Each strategy checks if it's the right window before evaluating signals, making frequent triggers safe.

---

## 6. Architectural Weaknesses & Technical Debt

### 6.1 Monolithic `live_trader.py`

964 lines containing 9 strategies, regime detection, GEX calculation, risk state management, and the main dispatcher. Any change risks side effects. The ARCHITECTURE_V2.md document acknowledges this and proposes a plugin system, but migration has not started.

**Risk:** MEDIUM — the file works, but it's the single point of failure for the entire system.

### 6.2 No test suite

Zero automated tests. The `test_*.py` files are one-off scripts, not a test framework. No pytest, no CI test step.

**Risk:** HIGH — every code change is verified manually or not at all.

### 6.3 Credentials in `config.ini` (not env-only)

While `load_config()` supports env var overlay, the actual `config.ini` contains real API keys and is only protected by `.gitignore`. The `.env.example` references OANDA, suggesting the env-var pattern was established later.

**Risk:** MEDIUM — one accidental `git add -f config.ini` leaks everything.

### 6.4 Duplicate GitHub Actions workflows

`main.yml` and `paper-trade.yml` have overlapping cron schedules (`30 7`, `30 14`, `0 21` on weekdays). Both run `live_trader.py --broker alpaca --session all`. This means **double execution** of the same session on Alpaca.

**Risk:** HIGH — could cause duplicate orders if position checks race.

### 6.5 `exec()` for code reuse in research scripts

`conformal_overlay.py` and `macro_event_filter.py` use `exec(open("combined_3pillar.py").read(), g)` to import the combined P&L. This is fragile (path-dependent, suppresses output via contextlib).

**Risk:** LOW — research scripts only.

### 6.6 No database / persistent state store

All state is in JSON files in `logs/`. This works for a single-instance system but makes multi-venue coordination impossible. The `risk_state_*.json` files are per-broker, but there's no transactional guarantee.

**Risk:** LOW — acceptable for current scale.

### 6.7 140+ Python files, no package structure

Everything is flat in the repo root. No `src/`, no `setup.py`, no `pyproject.toml`. The `risk/` package is the only structured module.

**Risk:** LOW — works but makes imports fragile and the repo hard to navigate.

### 6.8 Inconsistent path handling

`live_trader.py` uses `os.path` throughout. `broker.py` uses `os.path`. `risk/risk_profile_loader.py` uses `pathlib.Path`. `dashboard/app.py` uses `pathlib.Path`. Mixed patterns.

**Risk:** LOW — cosmetic, but indicates incremental modernization.

### 6.9 No structured logging

Logs are plain text lines parsed by regex in `check_health.py` and `dashboard/app.py`. No JSON logging, no structured fields. Every log consumer is fragile to format changes.

**Risk:** MEDIUM — format drift breaks monitoring silently.

### 6.10 Dead code: S6 references

Multiple files (`fix_s6entry.py`, `fix_s6exit.py`, `patch_s6_dict.py`) reference an "S6" strategy that doesn't exist in `live_trader.py`. S6 was apparently dropped during development.

**Risk:** NONE — dead files, just clutter.

---

## 7. Safe vs. Unsafe Components

| Component | Safety Rating | Rationale |
|-----------|---------------|-----------|
| Strategy logic (S1–S5, BTC, xsmom, overnight) | 🟢 SAFE | Validated via walk-forward, defensive entry checks, broker-side stops |
| Risk engine (DD-throttle, kill-switches) | 🟢 SAFE | Per-broker state, conservative defaults, monthly reset |
| Broker layer (abstract + adapters) | 🟢 SAFE | Clean interface, `place_order_safe` prevents double-sends |
| Alert system | 🟢 SAFE | Multi-channel with console fallback — never silently drops |
| MT5 adapter | 🟢 SAFE | Lot conversion, symbol mapping, timezone handling |
| Alpaca adapter | 🟢 SAFE | Paper-first default, clean SDK usage |
| Binance adapter | 🟢 SAFE | Correct HMAC signing, public/private endpoint split |
| cTrader adapter | 🟡 SCAFFOLD | Account info works; execution untested |
| Tradovate adapter | 🟡 SCAFFOLD | Auth works; execution untested |
| GitHub Actions scheduling | 🔴 RISK | Duplicate workflows may cause double-execution |
| Config management | 🟡 RISK | Real credentials in gitignored file; env overlay exists but underused |
| State persistence | 🟢 SAFE | JSON files with try/except, per-broker isolation |
| Logging | 🟡 FRAGILE | Regex-parsed text logs; no structured logging |
| Monitoring tools | 🟢 SAFE | 5 complementary tools covering different failure modes |
| Dashboard | 🟢 SAFE | Pure read-only consumer |

---

## 8. Recommendations (prioritized)

### Immediate (risk to live trading)

1. **Remove or disable `paper-trade.yml`** — it duplicates `main.yml` crons and may cause double-execution.
2. **Audit Alpaca for duplicate orders** — check fill history for pairs within minutes of each other.

### Short-term (code hygiene)

3. **Archive LEGACY scripts** to an `archive/` or `_legacy/` directory (paper_trade.py, Procfile, .env.example, SMA scripts, backup files).
4. **Delete DEBUG one-timers** (fix_s6*, patch_*, debug_weights*, final_sma_test*, add_debug, test_print).
5. **Remove `sweep_backtest.py .py`** (space in filename, clearly accidental).

### Medium-term (architecture)

6. **Add a pytest test suite** — at minimum, test `broker.py` interfaces, `load_config()`, risk state round-trip.
7. **Migrate `live_trader.py` to a package** — split strategies into `strategies/s1_asian_sweep.py`, etc.
8. **Add JSON structured logging** — make monitoring reliable.
9. **Move all path handling to pathlib** — consistency.

### Long-term (from ARCHITECTURE_V2.md)

10. **Implement the V2 plugin architecture** — strategies as self-contained plugins with declared exit contracts.
11. **Unify backtest and live strategy definitions** — eliminate divergence risk.
