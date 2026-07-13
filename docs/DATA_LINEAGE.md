# DATA LINEAGE -- every dataset traced

_2026-07-13. No code change. Source -> strategy -> experiment -> validator ->
shadow -> dashboard. "live" data is fetched at runtime by the broker adapters;
the .csv files are the frozen research-history replays the audits run against._

## Primary price histories
| dataset | source | strategy(s) | experiment(s) | validated by | shadowed by | dashboard |
|---|---|---|---|---|---|---|
| `qqq_hourly_7y.csv` | Alpaca ext-hours, spliced w/ live fetch | **S1, S5** | weekend_exposure, S5 re-entry, part_a_universe | LIVE_TRADING_PARITY, STRATEGY_VALIDATION_AUDIT | ETF_FORWARD_SHADOW (S1_/S5_ QQQ) | STRATEGIES, SHADOW, EXECUTION |
| `qqq_hourly_7y.csv` (daily agg) | derived in-engine | **S3** | weekend_exposure | S3_VALIDATION_REVIEW | — | STRATEGIES |
| `gld_hourly_7y.csv` + live daily GLD | Alpaca / yfinance | **S2** (daily-FVG) | (none direct) | STRATEGY_VALIDATION_AUDIT, FINDINGS | — | STRATEGIES |
| `spy_hourly_7y.csv` | Alpaca | **S4** (+ S1 confirm) | intraday_momentum, verify_liveness | LIVE_TRADING_PARITY | — | STRATEGIES |
| `btc_1h.csv` + live Binance/MT5 | Binance spot / Pepperstone CFD | **BTC, BTCTREND** | part_c_tsmom, btc_sweep_test | STRATEGY_VALIDATION_AUDIT (venue caveat) | — | STRATEGIES |
| `aapl/msft/nvda/iwm/xlk_hourly_7y.csv`, `multi_etf_hourly.csv` | Alpaca | (universe candidates) | **part_a_universe** | ETF_FORWARD_SHADOW_REVIEW | shadow_signals.csv (9 survivors) | SHADOW, RESEARCH |

## Derived / state datasets
| dataset | source | consumed by | validates/feeds | dashboard |
|---|---|---|---|---|
| `state/macro_daily.csv` | macro_state.py (yfinance VIX/VIX3M/etc.) | shadow_etf.py gates, MACRO_FILTER_REVIEW | VIX term-structure gate (WAITING) | SHADOW (gate cols) |
| `research/results/shadow_signals.csv` | shadow_etf.py (daily) | evidence_report, dashboard | ETF_FORWARD_SHADOW_REVIEW | SHADOW, HOME feeds |
| `research/results/etf_streams.csv` | part_a_universe | evidence_report (research expectation) | month-end verdict | SHADOW |
| `logs/fills.csv` | fill_ledger.py (live order boundary) | analyze_execution, dashboard EXECUTION | execution-cost measurement (prop blocker #2) | EXECUTION, HOME, STRATEGIES |
| `gex_history.csv` | GEX provider snapshot | S1 GEX gate; analyze_weak_strategies | (gating input, not a strategy) | — |
| `skew_history.csv` | IV skew snapshot | iv_skew_ab (rejected) | graveyard | — |

## Higher-resolution / reference (mostly dormant)
| dataset | role | status |
|---|---|---|
| `qqq_1min_7y.csv`, `qqq_15min_7y.csv`, `spy_15min_7y.csv` | master_backtest.py fine-grained lineage; ORB 1-min reference | reference only -- live runs on hourly; keep for provenance |
| `btcusdt_1h.csv`, `ethusdt_1h.csv` | superseded crypto history | 0 references -- archive candidate (see REPO_CLEANUP) |
| `paper_status.csv` | paper_trade_master.py bookkeeping | legacy paper-loop artifact |

## Runtime (non-file) data sources
- **Broker bars:** `get_bars()` on Alpaca / MT5 / Binance adapters -- the LIVE
  equivalent of the .csv histories (BAR-COUNT contract). This is what production
  actually trades on; the .csv files exist to replay the same logic offline.
- **Regime:** VIX / VIX3M / SPY / QQQ via yfinance at session start (live_trader).
- **GEX:** fetched into the S1 gate at runtime.

## Trust boundaries
- **Validated:** the 7y .csv histories underpin every gauntlet; a strategy is only
  "validated" against the dataset in its row above. Cross-dataset generalization is
  explicitly NOT assumed (e.g. S2 gold weekend gaps are not inferred from QQQ).
- **Shadowed:** only `shadow_signals.csv` is forward-evidence; everything else is
  backtest history. The month-end report merges shadow + `fills.csv` (live) as the
  single source of truth.
- **Venue divergence:** BTC and the CFD side of S5 trade a different feed than they
  were validated on -- flagged in STRATEGY_VALIDATION_AUDIT, measured via fills.csv.

Master index: [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) · machine twin `knowledge_graph.json`.
