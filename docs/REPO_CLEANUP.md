# REPOSITORY ORGANIZATION AUDIT

_2026-07-13. Recommendations only -- **NO deletions performed.** Root holds 144 .py
files; production imports only 8. The rest is research/experiment sprawl. This lists
what is safe to archive (Phase-2 of MIGRATION_PLAN), never what to delete blindly._

## Do NOT touch (production surface -- 8 modules + entrypoint)
`live_trader.py`, `broker.py`, `mt5_broker.py`, `alpaca_broker.py`,
`binance_broker.py`, `ctrader_broker.py`, `tradovate_broker.py`, `alerts.py`,
`fill_ledger.py` -- imported by the live engine. Frozen.

## 1. Confirmed orphans (0 references anywhere -- safe to archive first)
`analyze_weak_simple.py`, `analyze_weak_strategies.py`, `check_nikkei.py`,
`perf_test.py`, `walk_debug.py`, `walk_test.py` -- scratch/debug scripts, no
importer, no doc reference. **Recommend:** move to `archive/scratch/`.

## 2. Dead datasets (0 code references)
`btcusdt_1h.csv`, `ethusdt_1h.csv` -- superseded by `btc_1h.csv` / live Binance
fetch. **Recommend:** move to `archive/data/` (keep -- cheap, and crypto history
is annoying to refetch; just get them out of root).

## 3. Duplicate / superseded backtest lineages (~50 files)
Two lineages are canonical and referenced by docs: **`master_backtest.py`** and
**`full_yearly.py`**. The rest are earlier one-off explorations, most now in the
graveyard (FINDINGS / RESEARCH_GRAVEYARD_AUDIT). High-duplication clusters:
- **gold:** `gold_backtest.py`, `gold_backtest_v2.py` (v2 supersedes v1)
- **sweep variants:** `sweep_v2.py`, `sweep_v3_15min.py`, `sweep_combined.py`,
  `sweep_per_instrument.py`, `combined_backtest.py`, `combined_3pillar.py`
- **ensemble:** `ensemble_backtest.py`, `ensemble_backtest_test.py`
- **ORB/mean-rev:** `orb_backtest.py`, `orb_1min.py`, `eurusd_orb_backtest.py`,
  `mean_reversion_test.py`, `meanrev_signal_test.py`, `mr_gap_test.py`, `dax_meanrev_test.py`
**Recommend:** move to `archive/backtests/`, keep `master_backtest.py` +
`full_yearly.py` in root. Do NOT delete -- they are the provenance trail the
validation audits cite.

## 4. Obsolete / dated reports (superseded snapshots)
- `docs/DAILY_OPS_2026-07-10.md` -- one-day snapshot; the live `DAILY_OPS_REPORT.md`
  is regenerated. **Recommend:** move to `docs/archive/`.
- `docs/NO_REAL_TRADES_ROOT_CAUSE.md`, `docs/LIVE_TRADE_REVIEW.md` -- superseded by
  `LOSING_TRADE_FORENSICS.md` + `SETUP_SUPPLY_ANALYSIS.md`. **Recommend:** keep
  (historical root-cause value) but cross-link as superseded.
- `docs/MONTH_1_LIVE_REPORT.md` -- placeholder until 2026-08-16; will populate at
  month-end. Keep.

## 5. Duplicate dashboard logic
`dashboard/app_legacy.py` (the 461-line pre-cockpit skeleton) is fully superseded
by `dashboard/app.py`. **Recommend:** move to `archive/` after one more session's
confidence in the cockpit. `dashboard/COMMAND_CENTER.md` (markdown) and the
Streamlit HOME page overlap by design (offline vs interactive) -- keep both.
Stray `dashboard/streamlit*.log` files are test artifacts -- **gitignore them**.

## 6. Broken links
**None.** All 41 `docs/*.md` internal markdown links resolve.

## 7. Suggested target layout (Phase-2, one `git mv` batch, reversible)
```
archive/backtests/   ~50 superseded lineage scripts
archive/scratch/     6 orphan/debug scripts
archive/data/        2 dead crypto csvs
docs/archive/        dated one-off reports
```
Root would drop from 144 .py to ~90 (production + canonical lineages + live tools).

## Non-recommendations (leave alone)
- The `.csv` history files that ARE referenced (qqq/spy/gld/etc.) -- the audits
  replay them; moving them means updating paths in live experiments. Not worth it.
- Anything under `research/`, `scripts/`, `vault/` -- already organized.

**Nothing here is executed. This is a proposal for a single reviewable `git mv`
batch, to be run outside the evidence window (it touches no signal code, but keep
the diff clean and dated).**
