# CODE MAP — nas100-trader

> Complete inventory of every Python file, script, config, and data source in the repository.
> Each entry is classified: **[PRODUCTION]**, **[LEGACY]**, **[RESEARCH]**, **[DEBUG]**, **[UNUSED]**, **[DUPLICATE]**.

---

## 1. Core Trading System (PRODUCTION)

| File | Lines | Classification | Purpose |
|------|-------|----------------|---------|
| `live_trader.py` | 964 | **[PRODUCTION]** | Main entrypoint. All strategies (S1–S5, BTC, xsmom, overnight, btctrend, sweep basket), risk engine (DD-throttle, kill-switches), regime detection, session dispatcher. |
| `broker.py` | 184 | **[PRODUCTION]** | Abstract `Broker` base class, `DryRunBroker` wrapper, `load_config()`, `_load_local_csv()` fallback. Defines the `place_order_safe()` retry-with-backoff execution path. |
| `mt5_broker.py` | ~250 | **[PRODUCTION]** | MetaTrader 5 adapter (Pepperstone/FTMO). CFD symbol mapping (QQQ→US100, GLD→XAUUSD, BTC→BTCUSD). Windows-only. |
| `alpaca_broker.py` | ~120 | **[PRODUCTION]** | Alpaca paper adapter. ETF symbols pass through unmapped. Uses alpaca-py SDK. |
| `binance_broker.py` | ~200 | **[PRODUCTION]** | Binance spot adapter for BTC sweep/trend pillars. Public klines for bars, HMAC-SHA256 signed for trades. |
| `ctrader_broker.py` | ~200 | **[PRODUCTION]** | cTrader Open API adapter (FTMO). Scaffold with REST account-info; full execution requires protobuf WS library. |
| `tradovate_broker.py` | ~180 | **[PRODUCTION]** | Tradovate futures adapter (Apex/Topstep). Scaffold; micro-futures (MNQ/MES/MGC). |
| `alerts.py` | 84 | **[PRODUCTION]** | Multi-channel alert dispatcher: Telegram, email, console. Called by broker and live_trader on fills, failures, kill-switch events. |
| `config.ini` | — | **[PRODUCTION]** | Live credentials (gitignored). Sections: alpaca, ctrader, tradovate, binance, mt5, alerts, risk. |
| `config.example.ini` | — | **[PRODUCTION]** | Template with placeholder credentials. |
| `requirements.txt` | 6 | **[PRODUCTION]** | Python dependencies: requests, pandas, pytz, yfinance, matplotlib, alpaca-py, scipy. |

---

## 2. Risk Governance (PRODUCTION)

| File | Lines | Classification | Purpose |
|------|-------|----------------|---------|
| `risk/__init__.py` | 10 | **[PRODUCTION]** | Package docstring. Mode-based risk governance layer. |
| `risk/risk_profile_loader.py` | 140 | **[PRODUCTION]** | Loads risk profiles from YAML. Selects active profile (challenge/funded/live) via config.ini or env var. Caches with mtime invalidation. |
| `risk/challenge_mode.py` | ~30 | **[PRODUCTION]** | Challenge-mode risk rules (tighter DD, daily loss limits). |
| `risk/funded_mode.py` | ~20 | **[PRODUCTION]** | Funded-mode risk rules (relaxed limits for passed challenge). |
| `risk/live_mode.py` | ~20 | **[PRODUCTION]** | Live-mode risk rules (standard limits). |
| `config/risk_profiles.yaml` | ~90 | **[PRODUCTION]** | Risk profile definitions: default, live, challenge, funded. Risk multipliers, DD caps, loss limits per mode. |

---

## 3. Operations & Monitoring (PRODUCTION)

| File | Lines | Classification | Purpose |
|------|-------|----------------|---------|
| `status.py` | 65 | **[PRODUCTION]** | One-command venue health check. Verifies MT5 connection, symbol maps, Telegram wiring, scheduled tasks, log tails. Run on VPS. |
| `s5_watchdog.py` | 50 | **[PRODUCTION]** | Hourly canary for S5 ORB pillar. Alerts if the 9:00 ET opening-range bar is missing from MT5 feed. |
| `weekly_report.py` | 93 | **[PRODUCTION]** | Friday summary of Alpaca paper-trading activity → Telegram. Scheduled via GitHub Actions. |
| `check_health.py` | 191 | **[DEBUG/OPS]** | Diagnoses "why no trades?" from live logs. Distinguishes scheduler failure vs gate-closed vs normal silence. |
| `verify_liveness.py` | 153 | **[DEBUG]** | Replays real price history through strategy entry conditions to prove code paths can fire. |
| `perf_report.py` | ~200 | **[DEBUG]** | Full-system performance report with QuantStats tearsheet. Parses live trade logs. |

---

## 4. Schedulers & Deployment

| File | Classification | Purpose |
|------|----------------|---------|
| `schedule_mt5.ps1` | **[PRODUCTION]** | Registers all Windows Scheduled Tasks on VPS (hourly sessions, overnight, BTC, rebalance). |
| `setup_vps.ps1` | **[LEGACY]** | Git-free VPS setup via ZIP download. Superseded by `setup_vps_git.ps1`. |
| `setup_vps_git.ps1` | **[PRODUCTION]** | Converts VPS folder to git clone, registers scheduled tasks, installs git if missing. |
| `update_vps.ps1` | **[PRODUCTION]** | VPS updater: sync from GitHub, optional validation battery. Self-updating. |
| `.github/workflows/main.yml` | **[PRODUCTION]** | GitHub Actions: 5 cron schedules (Asian, ORB, EOD, overnight enter/exit). Runs on Ubuntu. |
| `.github/workflows/paper-trade.yml` | **[DUPLICATE]** | Overlaps with `main.yml` — same cron times, subset of functionality. Appears to be an earlier version. |
| `weekly-report.yml` | **[PRODUCTION]** | GitHub Actions: Friday 22:00 UTC weekly report. |
| `Procfile` | **[LEGACY]** | Railway.app worker entrypoint (`python3 live_trader.py`). From the original OANDA deployment. |
| `run.sh` | **[PRODUCTION]** | Local paper-run convenience script. |
| `.env.example` | **[LEGACY]** | OANDA env var template. References OANDA_API_KEY, OANDA_ACCOUNT_ID. |
| `.gitignore` | **[PRODUCTION]** | Excludes credentials, logs, data, CSVs, PNGs, RD-Agent. |

---

## 5. Dashboard

| File | Classification | Purpose |
|------|----------------|---------|
| `dashboard/app.py` | **[PRODUCTION]** | Read-only Streamlit dashboard. Health cards, risk table, recent orders/fills, warnings/errors, last 100 log lines. |
| `dashboard/README.md` | **[PRODUCTION]** | Dashboard documentation. |
| `requirements-dashboard.txt` | **[PRODUCTION]** | Dashboard dependencies: streamlit, streamlit-autorefresh. |
| `dashboard/test_funcs.py` | **[DEBUG]** | Test functions for dashboard. |

---

## 6. Data Files

| File | Classification | Purpose |
|------|----------------|---------|
| `qqq_hourly_7y.csv` | **[PRODUCTION]** | 7-year QQQ hourly bars (strategy data + fallback). |
| `qqq_1min_7y.csv` | **[PRODUCTION]** | 7-year QQQ 1-minute bars. |
| `qqq_15min_7y.csv` | **[PRODUCTION]** | 7-year QQQ 15-minute bars. |
| `spy_hourly_7y.csv` | **[PRODUCTION]** | 7-year SPY hourly bars. |
| `spy_15min_7y.csv` | **[PRODUCTION]** | 7-year SPY 15-minute bars. |
| `gld_hourly_7y.csv` | **[PRODUCTION]** | 7-year GLD hourly bars. |
| `aapl_hourly_7y.csv` | **[PRODUCTION]** | 7-year AAPL hourly bars (sweep basket). |
| `msft_hourly_7y.csv` | **[PRODUCTION]** | 7-year MSFT hourly bars (sweep basket). |
| `nvda_hourly_7y.csv` | **[PRODUCTION]** | 7-year NVDA hourly bars (sweep basket). |
| `iwm_hourly_7y.csv` | **[PRODUCTION]** | 7-year IWM hourly bars (sweep basket). |
| `xlk_hourly_7y.csv` | **[PRODUCTION]** | 7-year XLK hourly bars (sweep basket). |
| `multi_etf_hourly.csv` | **[PRODUCTION]** | Combined ETF hourly data. |
| `btc_1h.csv` | **[RESEARCH]** | BTC hourly data (older dataset). |
| `btcusdt_1h.csv` | **[RESEARCH]** | BTCUSDT hourly data. |
| `ethusdt_1h.csv` | **[RESEARCH]** | ETHUSDT hourly data. |
| `gex_history.csv` | **[RESEARCH]** | Historical GEX data (stops 2023). |
| `skew_history.csv` | **[RESEARCH]** | Historical skew data. |

---

## 7. State Files (runtime, gitignored)

| File | Classification | Purpose |
|------|----------------|---------|
| `logs/risk_state.json` | **[PRODUCTION]** | Default broker risk state (peak equity, month-start equity). |
| `logs/risk_state_alpaca.json` | **[PRODUCTION]** | Alpaca-specific risk state. |
| `logs/risk_state_binance.json` | **[PRODUCTION]** | Binance-specific risk state. |
| `logs/btc_state.json` | **[PRODUCTION]** | BTC sweep position state (active, entry, stop, target, qty). |
| `logs/ovn_state.json` | **[PRODUCTION]** | Overnight strategy state (active, qty, entry). |
| `logs/btc_trend_state.json` | **[PRODUCTION]** | BTC trend strategy state (qty, price). |
| `logs/trader.log` | **[PRODUCTION]** | Main trading log (RotatingFileHandler, 5MB × 5 backups). |
| `logs/hunt_overnight.log` | **[LEGACY]** | Overnight hunt log. |

---

## 8. Backtest & Research Scripts

### Primary Backtests (validated, feed into live trading)

| File | Classification | Purpose |
|------|----------------|---------|
| `combined_3pillar.py` | **[RESEARCH]** | Combined 3-pillar daily P&L series. Exec'd by other research scripts. |
| `combined_backtest.py` | **[RESEARCH]** | Combined strategy backtest. |
| `combined_yearly.py` | **[RESEARCH]** | Yearly breakdown of combined performance. |
| `full_yearly.py` | **[RESEARCH]** | Full yearly backtest (+ 4 backup variants). |
| `master_backtest.py` | **[RESEARCH]** | Master backtest harness. |
| `walkforward.py` | **[RESEARCH]** | Walk-forward analysis framework. |
| `open_breakout_walkforward.py` | **[RESEARCH]** | ORB walk-forward (7/7 windows, Sharpe 3.21). |

### Strategy-Specific Backtests

| File | Classification | Purpose |
|------|----------------|---------|
| `orb_backtest.py` | **[RESEARCH]** | ORB strategy backtest (original). |
| `orb_1min.py` | **[RESEARCH]** | 1-minute ORB (the losing version). |
| `orb_5min.py` | **[RESEARCH]** | 5-minute ORB. |
| `abnormal_volume_backtest.py` | **[RESEARCH]** | S3 abnormal volume backtest. |
| `vwap_backtest.py` | **[RESEARCH]** | VWAP backtest. |
| `vwap_sweep_backtest.py` | **[RESEARCH]** | VWAP sweep backtest. |
| `gold_backtest.py` | **[RESEARCH]** | Gold strategy v1. |
| `gold_backtest_v2.py` | **[RESEARCH]** | Gold strategy v2. |
| `btc_asian_sweep.py` | **[RESEARCH]** | BTC Asian sweep backtest. |
| `btc_funding_reversal.py` | **[RESEARCH]** | BTC funding reversal. |
| `btc_funding_m2.py` | **[RESEARCH]** | BTC funding M2. |
| `btc_meanrev.py` | **[RESEARCH]** | BTC mean reversion. |
| `volume_profile_backtest.py` | **[RESEARCH]** | Volume profile. |
| `volume_profile_m1.py` | **[RESEARCH]** | Volume profile M1. |
| `vix_divergence_backtest.py` | **[RESEARCH]** | VIX divergence. |
| `nq_futures_backtest.py` | **[RESEARCH]** | NQ futures. |
| `multi_etf_backtest.py` | **[RESEARCH]** | Multi-ETF. |
| `multi_asset_orb.py` | **[RESEARCH]** | Multi-asset ORB. |
| `eurusd_orb_backtest.py` | **[RESEARCH]** | EURUSD ORB. |
| `gamma_backtest.py` | **[RESEARCH]** | Gamma (GEX) backtest. |
| `xsmom_enhanced.py` | **[RESEARCH]** | Enhanced cross-sectional momentum. |
| `xsmom_proper.py` | **[RESEARCH]** | Proper xsmom (validated → `run_xsmom` in live_trader). |
| `commodity_carry.py` | **[RESEARCH]** | Commodity carry. |
| `funding_carry.py` | **[RESEARCH]** | Funding carry v1. |
| `funding_carry_realistic.py` | **[RESEARCH]** | Realistic funding carry. |
| `funding_carry_strategy.py` | **[RESEARCH]** | Funding carry strategy. |

### Sweep / Parameter Search

| File | Classification | Purpose |
|------|----------------|---------|
| `sweep_backtest.py` | **[RESEARCH]** | Parameter sweep. |
| `sweep_backtest_7y.py` | **[RESEARCH]** | 7-year sweep. |
| `sweep_backtest_hourly_7y.py` | **[RESEARCH]** | Hourly 7-year sweep. |
| `sweep_combined.py` | **[RESEARCH]** | Combined sweep. |
| `sweep_per_instrument.py` | **[RESEARCH]** | Per-instrument sweep. |
| `sweep_v2.py` | **[RESEARCH]** | Sweep v2. |
| `sweep_v3_15min.py` | **[RESEARCH]** | 15-min sweep v3. |
| `alpaca_universe_sweep.py` | **[RESEARCH]** | Alpaca universe sweep. |
| `btc_sweep_test.py` | **[RESEARCH]** | BTC sweep test. |
| `futures_sweep_test.py` | **[RESEARCH]** | Futures sweep. |
| `eu_indices_sweep.py` | **[RESEARCH]** | EU indices sweep. |
| `reconcile_sweep.py` | **[RESEARCH]** | Sweep reconciliation. |

### Validation / Verification

| File | Classification | Purpose |
|------|----------------|---------|
| `cfd_validate.py` | **[RESEARCH]** | Validates QQQ→US100 CFD port (symbol mapping, price correlation). |
| `nikkei_validate.py` | **[RESEARCH]** | Nikkei validation. |
| `btc_validate.py` | **[RESEARCH]** | BTC validation. |
| `cac_meanrev.py` | **[RESEARCH]** | CAC mean reversion. |
| `dax_meanrev.py` | **[RESEARCH]** | DAX mean reversion. |
| `dax_meanrev_test.py` | **[RESEARCH]** | DAX mean reversion test. |
| `london_breakout_test.py` | **[RESEARCH]** | London breakout. |
| `asian_breakout_test.py` | **[RESEARCH]** | Asian breakout. |
| `intraday_momentum_test.py` | **[RESEARCH]** | Intraday momentum. |
| `mean_reversion_test.py` | **[RESEARCH]** | Mean reversion. |
| `mean_reversion_basket.py` | **[RESEARCH]** | Mean reversion basket. |
| `mean_reversion_portfolio.py` | **[RESEARCH]** | Mean reversion portfolio. |
| `mr_gap_test.py` | **[RESEARCH]** | Mean-reversion gap test. |
| `meanrev_signal_test.py` | **[RESEARCH]** | Mean-reversion signal test. |
| `pairs_test.py` | **[RESEARCH]** | Pairs test. |
| `orderflow_test.py` | **[RESEARCH]** | Orderflow test. |
| `voc_timing_test.py` | **[RESEARCH]** | VOC timing test. |
| `dix_filter_test.py` | **[RESEARCH]** | DIX filter test. |
| `dynamic_exits_test.py` | **[RESEARCH]** | Dynamic exits test. |
| `gamma_filter_test.py` | **[RESEARCH]** | Gamma filter test. |
| `iv_skew_ab.py` | **[RESEARCH]** | IV skew A/B test. |

### Strategy Analysis & Overlays

| File | Classification | Purpose |
|------|----------------|---------|
| `conformal_overlay.py` | **[RESEARCH]** | Conformal risk overlay (vol-target + DD-throttle). |
| `macro_event_filter.py` | **[RESEARCH]** | Macro event filter analysis (FOMC/NFP/CPI). |
| `decay_aware_strategy_management.py` | **[UNUSED]** | Alpha decay monitoring. Not wired into live trading. |
| `pillar_allocation.py` | **[RESEARCH]** | Pillar allocation analysis. |
| `compare_strategies.py` | **[RESEARCH]** | Strategy comparison. |
| `ensemble_backtest.py` | **[RESEARCH]** | Ensemble backtest. |
| `ensemble_backtest_test.py` | **[RESEARCH]** | Ensemble backtest tests. |
| `break_even_sharpe.py` | **[RESEARCH]** | Break-even Sharpe analysis. |
| `edge_hunt.py` | **[RESEARCH]** | Edge hunt harness. |

### CoT / Cross-Sectional

| File | Classification | Purpose |
|------|----------------|---------|
| `cot_hedging_signal.py` | **[RESEARCH]** | CoT hedging signal. |
| `cot_oil_strategy.py` | **[RESEARCH]** | CoT oil strategy. |
| `cross_sectional_cot.py` | **[RESEARCH]** | Cross-sectional CoT v1. |
| `cross_sectional_cot_v2.py` | **[RESEARCH]** | Cross-sectional CoT v2. |
| `crypto_commodity_hunt.py` | **[RESEARCH]** | Crypto/commodity edge hunt. |

---

## 9. Legacy / Superseded Scripts

| File | Classification | Purpose |
|------|----------------|---------|
| `paper_trade.py` | **[LEGACY]** | Original OANDA NAS100 Asian Sweep paper trader (Railway.app). Superseded by `live_trader.py`. |
| `paper_trade_master.py` | **[LEGACY]** | Multi-strategy paper trader. Superseded by `live_trader.py`. |
| `alpaca_paper_trader.py` | **[LEGACY]** | Standalone S3 Alpaca paper trader. Logic now in `live_trader.py --session eod`. |
| `sma_strategy.py` | **[LEGACY]** | SMA strategy (abandoned). |
| `sma_test.py` | **[LEGACY]** | SMA test. |
| `sma_vol_test.py` | **[LEGACY]** | SMA + volume test. |
| `sma_vol_test2.py` | **[LEGACY]** | SMA + volume test v2. |
| `sma_final.py` | **[LEGACY]** | SMA final (abandoned). |
| `walkforward_sma.py` | **[LEGACY]** | SMA walk-forward. |
| `live_trader.py.bak` | **[LEGACY]** | Backup of live_trader.py. |
| `full_yearly.py.backup_*` (×4) | **[LEGACY]** | Backups of full_yearly.py at various stages. |
| `sweep_backtest.py .py` | **[LEGACY]** | Misnamed duplicate (space in filename). |
| `setup_telegram.py` | **[LEGACY]** | One-time Telegram setup script. |

---

## 10. Debug / Patch Scripts (one-time use)

| File | Classification | Purpose |
|------|----------------|---------|
| `add_debug.py` | **[DEBUG]** | One-time debug patch. |
| `debug_s5s.py` | **[DEBUG]** | Debug S5 strategy. |
| `debug_weights.py` | **[DEBUG]** | Debug portfolio weights. |
| `debug_weights2.py` | **[DEBUG]** | Debug weights v2. |
| `diag_live.py` | **[DEBUG]** | Diagnose live trading issues. |
| `fix_s6entry.py` | **[DEBUG]** | Fix S6 entry (S6 was dropped). |
| `fix_s6exit.py` | **[DEBUG]** | Fix S6 exit. |
| `fix_sma.py` | **[DEBUG]** | Fix SMA. |
| `modify_sma.py` | **[DEBUG]** | Modify SMA. |
| `patch_s6_dict.py` | **[DEBUG]** | Patch S6 dictionary. |
| `patch_strats_and_colors.py` | **[DEBUG]** | Patch strategy colors. |
| `protect_positions.py` | **[LEGACY]** | One-time MT5 SL cleanup. |
| `quick_check.py` | **[DEBUG]** | Quick parameter check. |
| `simple_strategy_check.py` | **[DEBUG]** | Simple strategy check. |
| `final_simple_check.py` | **[DEBUG]** | Final simple check. |
| `final_sma_test.py` | **[DEBUG]** | Final SMA test series. |
| `final_sma_test_fixed.py` | **[DEBUG]** | Fixed variant. |
| `final_sma_test_final.py` | **[DEBUG]** | "Final" final variant. |
| `final_sma_test_final_fixed.py` | **[DEBUG]** | Truly final fixed variant. |
| `test_doc_strategies.py` | **[DEBUG]** | Strategy documentation test. |
| `test_order.py` | **[DEBUG]** | Order placement test. |
| `test_print.py` | **[DEBUG]** | Print test. |
| `test_quality.py` | **[DEBUG]** | Quality test. |
| `test_weights.py` | **[DEBUG]** | Weights test. |

---

## 11. Data Utilities

| File | Classification | Purpose |
|------|----------------|---------|
| `download_data.py` | **[PRODUCTION]** | Download OHLCV data from various sources. |
| `fetch_dukascopy.py` | **[RESEARCH]** | Fetch Dukascopy historical data. |
| `fetch_mt5_history.py` | **[PRODUCTION]** | Fetch historical bars from MT5 (bridge for backtesting on broker-real data). |

---

## 12. Prop Firm / Simulation

| File | Classification | Purpose |
|------|----------------|---------|
| `prop_sim.py` | **[RESEARCH]** | Prop firm challenge simulator. |
| `prop_ev_sim.py` | **[RESEARCH]** | Prop firm EV simulation. |
| `prop_firm_optimizer.py` | **[RESEARCH]** | Prop firm parameter optimizer. |
| `s3_challenge_sim.py` | **[RESEARCH]** | S3 strategy challenge simulation. |

---

## 13. Documentation

| File | Classification | Purpose |
|------|----------------|---------|
| `ARCHITECTURE_V2.md` | **[PRODUCTION]** | Target architecture blueprint (V1 → V2 migration plan). |
| `CODE_INVENTORY.md` | **[LEGACY]** | Earlier code inventory. |
| `DATA_BRIDGE.md` | **[PRODUCTION]** | MT5 data bridge documentation. |
| `DECAY_AWARE_STRATEGY_GUIDE.md` | **[RESEARCH]** | Decay-aware strategy management guide. |
| `EDGE_HUNT_BRIEF.md` | **[RESEARCH]** | Edge hunt methodology. |
| `FINDINGS.md` | **[PRODUCTION]** | Validated research findings (strategy parameters, walk-forward results). |
| `HUNT_LOG.md` | **[RESEARCH]** | Edge hunt chronological log. |
| `LIVE_SAFETY_AUDIT.md` | **[PRODUCTION]** | Live trading safety audit. |
| `MIGRATION_PLAN.md` | **[PRODUCTION]** | V1→V2 migration plan. |
| `MT5_BRIDGE.md` | **[PRODUCTION]** | MT5 bridge setup guide. |
| `ORB_SHORT_IMPROVEMENT_RESEARCH.md` | **[RESEARCH]** | ORB short-side research. |
| `PROP_PLAN.md` | **[PRODUCTION]** | Prop firm trading plan. |
| `RUN.md` | **[PRODUCTION]** | How to run the system. |
| `S3_UPDATE_SUMMARY.md` | **[LEGACY]** | S3 update summary. |
| `SETUP.md` | **[PRODUCTION]** | Setup guide. |
| `STATUS.md` | **[PRODUCTION]** | System status. |
| `STRATEGY_ANALYSIS_SUMMARY.md` | **[RESEARCH]** | Strategy analysis summary. |
| `SWEEP_SUMMARY.md` | **[RESEARCH]** | Sweep results summary. |
| `VAULT_CONSOLIDATION_PLAN.md` | **[LEGACY]** | Data vault consolidation plan. |
| `docs/CHALLENGE_VS_FUNDED_VS_LIVE.md` | **[PRODUCTION]** | Risk mode comparison. |
| `docs/PROP_CHALLENGE_PLAYBOOK.md` | **[PRODUCTION]** | Prop challenge playbook. |
| `docs/RISK_MODE_ARCHITECTURE.md` | **[PRODUCTION]** | Risk mode architecture. |

---

## 14. Non-Project (OpenClaw / RD-Agent)

| File/Dir | Classification | Purpose |
|-----------|----------------|---------|
| `RD-Agent/` | **[EXTERNAL]** | Microsoft RD-Agent — separate open-source project, gitignored. |
| `AGENTS.md` | **[EXTERNAL]** | OpenClaw agent instructions. |
| `SOUL.md` | **[EXTERNAL]** | OpenClaw persona. |
| `IDENTITY.md` | **[EXTERNAL]** | OpenClaw identity. |
| `USER.md` | **[EXTERNAL]** | OpenClaw user profile. |
| `TOOLS.md` | **[EXTERNAL]** | OpenClaw local notes. |
| `HEARTBEAT.md` | **[EXTERNAL]** | OpenClaw heartbeat config. |
| `openclaw-workspace-state.json` | **[EXTERNAL]** | OpenClaw state. |
| `.claude/` | **[EXTERNAL]** | Claude settings. |
| `prompt.md`, `prompt.md.save` | **[EXTERNAL]** | Prompt files. |
| `test.md`, `audit_task.md` | **[EXTERNAL]** | Working notes. |

---

## Summary Counts

| Classification | Count |
|----------------|-------|
| **PRODUCTION** (core + ops + dashboard) | ~30 files |
| **RESEARCH** (backtests, analyses, experiments) | ~65 files |
| **LEGACY** (superseded, backups, one-time fixes) | ~20 files |
| **DEBUG** (one-time debug/patch scripts) | ~20 files |
| **UNUSED** (not wired into anything) | ~2 files |
| **DUPLICATE** (overlapping workflows) | ~1 file |
| **EXTERNAL** (OpenClaw, RD-Agent) | ~12 files |
| **Total Python files** | ~140 |
