"""
xsmom_proper.py — Cross-sectional momentum on a PROPER diverse universe.

The doc's P4 failed on 7 correlated names. Here we give it what it needs:
real dispersion. Two universes, both downloaded fresh from yfinance:

  A) 11 SPDR sector ETFs (XLK XLF XLE XLV XLU XLP XLI XLB XLRE XLC XLY)
  B) 8 cross-asset sleeves (SPY QQQ IWM EFA EEM TLT GLD DBC) — stocks/intl/bonds/cmdty

Strategy: 12-1 month momentum, rank, long top ~30%, monthly rebalance, equal
weight, costs on. Run through the same six filters, IS (pre-2022) vs OOS (2022+).
Also report vs SPY buy-hold so we know if it actually adds anything.
"""

import pandas as pd
import numpy as np
import warnings
import yfinance as yf
from datetime import date
warnings.filterwarnings("ignore")

SLIP = 0.0010   # monthly rebalance, ETF — round-trip turnover cost
SECTORS = ["XLK","XLF","XLE","XLV","XLU","XLP","XLI","XLB","XLRE","XLC","XLY"]
CROSS   = ["SPY","QQQ","IWM","EFA","EEM","TLT","GLD","DBC"]


def monthly_closes(tickers, start="2010-01-01"):
    raw = yf.download(tickers, start=start, end=str(date.today()),
                      progress=False, auto_adjust=True)["Close"]
    if isinstance(raw, pd.Series): raw = raw.to_frame()
    m = raw.resample("ME").last()
    return m.dropna(how="all")


def run_xsmom(px, top_frac=0.30):
    """Return (monthly_return_series, trade_returns_with_dates)."""
    mom = px.shift(1) / px.shift(12) - 1
    rets, trades = [], []
    for i in range(12, len(px) - 1):
        dt = px.index[i + 1]
        score = mom.iloc[i].dropna()
        valid = px.iloc[i].notna() & px.iloc[i + 1].notna()
        avail = valid.index[valid]
        score = score[score.index.isin(avail)]
        if len(score) < 4:
            continue
        n = max(1, int(round(len(score) * top_frac)))
        top = score.sort_values(ascending=False).index[:n]
        fwd = (px.iloc[i + 1][top] / px.iloc[i][top] - 1).mean() - SLIP
        rets.append((dt, fwd))
        trades.append((dt, fwd))
    return rets, trades


def stats(rets, lo, hi):
    sel = [(d, r) for (d, r) in rets if lo <= d.year <= hi]
    if not sel: return None
    r = pd.Series([x[1] for x in sel])
    eq = (1 + r).cumprod()
    sharpe = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else 0
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    return dict(n=len(r), wr=(r > 0).mean(), ret=eq.iloc[-1] - 1, cagr=cagr,
                sharpe=sharpe, dd=(eq / eq.cummax() - 1).min())


def spy_bench(lo, hi):
    spy = monthly_closes(["SPY"])["SPY"].pct_change().dropna()
    spy = spy[(spy.index.year >= lo) & (spy.index.year <= hi)]
    eq = (1 + spy).cumprod()
    return dict(cagr=eq.iloc[-1] ** (12/len(spy)) - 1,
                sharpe=spy.mean()/spy.std()*np.sqrt(12),
                dd=(eq/eq.cummax()-1).min())


def gauntlet(name, rets):
    IS, OOS = stats(rets, 2010, 2021), stats(rets, 2022, 2026)
    print(f"\n{'='*64}\n{name}")
    for lab, m in [("IS  (2010-21)", IS), ("OOS (2022-26)", OOS)]:
        print(f"  {lab}: n={m['n']:3d} wr={m['wr']:.0%} CAGR={m['cagr']:+.1%} "
              f"Sharpe={m['sharpe']:.2f} maxDD={m['dd']:.1%}")
    b = spy_bench(2022, 2026)
    print(f"  SPY bench OOS : CAGR={b['cagr']:+.1%} Sharpe={b['sharpe']:.2f} maxDD={b['dd']:.1%}")
    checks = {
        "[01] OOS Sharpe>0.5": OOS["sharpe"] > 0.5,
        "[02] maxDD>-35%":     OOS["dd"] > -0.35,
        "[03] OOS Sharpe<2.5": OOS["sharpe"] < 2.5,
        "[04] not overfit":    OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
        "[05] >=30 trades":    OOS["n"] >= 30,
        "[06] IS Sharpe>0":    IS["sharpe"] > 0,
    }
    for k, v in checks.items(): print(f"    [{'PASS' if v else 'FAIL'}] {k}")
    beats = OOS["sharpe"] > b["sharpe"]
    print(f"  Beats SPY (risk-adj)? {'YES' if beats else 'NO'}")
    print(f"  >>> {'PASSES ALL SIX' if all(checks.values()) else 'REJECTED'}")


# ------------------- Parameter Sensitivity Sweep for Universe B -------------------
def daily_data(tickers, start="2010-01-01"):
    """Download daily adjusted close prices."""
    df = yf.download(tickers, start=start, end=str(date.today()),
                     progress=False, auto_adjust=True)["Close"]
    if isinstance(df, pd.Series): df = df.to_frame()
    return df.dropna(how="all")


def get_rebalance_dates(index, offset_day=None, month_end=False):
    """
    Given a DatetimeIndex (daily), return a list of dates that are either:
    - the `offset_day` trading day of each month (1,5,10) if offset_day is not None
    - the last trading day of each month if month_end=True
    Uses pandas CustomBusinessDay (Mon-Fri).
    """
    from pandas.tseries.offsets import CustomBusinessDay
    cbd = CustomBusinessDay(weekmask='Mon Tue Wed Thu Fri')
    # Determine the unique year-month periods in the index
    months = index.to_series().dt.to_period('M').unique()
    rebal = []
    for period in months:
        # First day of the month as Timestamp
        month_start = period.start_time
        if month_end:
            # Last business day of the month: go to next month start, subtract one business day
            month_end_date = month_start + pd.offsets.BMonthEnd(0)
            candidate = month_end_date
        else:
            # Offset by (offset_day-1) business days
            candidate = month_start + (offset_day - 1) * cbd
        # If the resulting date is in our index, keep it
        if candidate in index:
            rebal.append(candidate)
    return sorted(set(rebal))


def run_xsmom_sweep(px_daily, lookback_months, top_N, offset_day=None, month_end=False):
    """
    Run cross-sectional momentum with daily data, mimicking the original monthly logic:
    - lookback_months: lookback in months (converted to ~21 trading days per month)
    - top_N: number of top stocks to hold each period
    - offset_day: rebalance on the offset_day-th trading day of the month (1,5,10) (if month_end=False)
    - month_end: if True, rebalance on the last trading day of the month
    Returns daily strategy returns series.
    """
    # Approximate trading days per month
    td_per_month = 21
    # momentum looks at (previous month) / (month lookback+1 ago) - 1
    # In daily terms: shift(21) / shift(21*(lookback_months+1)) - 1
    mom = px_daily.shift(21) / px_daily.shift(21 * (lookback_months + 1)) - 1
    # Get rebalance dates
    rebals = get_rebalance_dates(px_daily.index, offset_day=offset_day, month_end=month_end)
    if len(rebals) < 2:
        return pd.Series(dtype=float)

    # Build weights matrix: equal weight top_N at each rebalance date, held until next rebal date
    weights = pd.DataFrame(0.0, index=px_daily.index, columns=px_daily.columns)
    for i in range(len(rebals) - 1):
        dt = rebals[i]
        if dt not in mom.index:
            continue
        score = mom.loc[dt].dropna()
        # Only consider stocks with non-NaN price at dt and next rebal date
        valid = px_daily.loc[dt].notna() & px_daily.loc[rebals[i+1]].notna()
        avail = valid.index[valid]
        score = score[score.index.isin(avail)]
        if len(score) < 4:
            continue
        n = min(top_N, len(score))
        top = score.sort_values(ascending=False).index[:n]
        weights.loc[dt, top] = 1.0 / n
    # Forward fill weights to next rebal date (exclusive)
    weights = weights.reindex(px_daily.index).ffill()
    # Calculate daily returns of assets
    assets_ret = px_daily.pct_change()
    # Portfolio return each day = sum(weights * assets_ret)
    port_ret = (weights * assets_ret).sum(axis=1)
    # Subtract slippage on rebalance dates (turnover cost)
    turnover = weights.diff().abs().sum(axis=1)
    slip_cost = turnover * SLIP
    port_ret = port_ret - slip_cost
    # Keep only returns from first rebal date to last
    mask = (px_daily.index >= rebals[0]) & (px_daily.index < rebals[-1])
    port_ret = port_ret.loc[mask]
    return port_ret


def sweep_universe_B():
    print("\n" + "="*80)
    print("PARAMETER SENSITIVITY SWEEP — Universe B (SPY QQQ IWM EFA EEM TLT GLD DBC)")
    print("="*80)
    px_daily = daily_data(CROSS)
    lookbacks = [6, 9, 12]
    topNs = [2, 3, 4]
    offsets = [1, 5, 10]
    results = []
    for lb in lookbacks:
        for tn in topNs:
            for off in offsets:
                strat_ret = run_xsmom_sweep(px_daily, lb, tn, offset_day=off, month_end=False)
                if strat_ret.empty:
                    continue
                # Convert daily returns to monthly for stats (approx)
                # Use resample to month-end compounding
                monthly = (1 + strat_ret).resample('ME').prod() - 1
                monthly_list = [(idx, val) for idx, val in monthly.items()]
                IS = stats(monthly_list, 2010, 2021)
                OOS = stats(monthly_list, 2022, 2026)
                if IS is None or OOS is None:
                    continue
                b = spy_bench(2022, 2026)
                checks = {
                    "Sharpe>0.5": OOS["sharpe"] > 0.5,
                    "maxDD>-35%": OOS["dd"] > -0.35,
                    "Sharpe<2.5": OOS["sharpe"] < 2.5,
                    "not overfit": OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
                    ">=30 trades": OOS["n"] >= 30,
                    "IS Sharpe>0": IS["sharpe"] > 0,
                }
                passes_all = all(checks.values())
                beats_spy = OOS["sharpe"] > b["sharpe"]
                results.append({
                    "lookback": lb,
                    "topN": tn,
                    "offset": off,
                    "OOS Sharpe": OOS["sharpe"],
                    "OOS CAGR": OOS["cagr"],
                    "OOS maxDD": OOS["dd"],
                    "Passes 6?": passes_all,
                    "Beats SPY?": beats_spy
                })
    # Print summary table
    print(f"{'LB':>4} {'TN':>4} {'Off':>4} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>8} {'6Pass':>6} {'BeatSPY':>8}")
    print("-"*70)
    for r in results:
        print(f"{r['lookback']:4d} {r['topN']:4d} {r['offset']:4d} "
              f"{r['OOS Sharpe']:8.2f} {r['OOS CAGR']:8.1%} {r['OOS maxDD']:8.1%} "
              f"{'YES' if r['Passes 6?'] else 'NO':>6} {'YES' if r['Beats SPY?'] else 'NO':>8}")
    # Determine robustness: count how many combos pass all 6 filters + beat SPY?
    robust_count = sum(1 for r in results if r["Passes 6?"] and r["Beats SPY?"])
    total = len(results)
    print(f"\nRobust combos (pass all six + beat SPY): {robust_count}/{total}")
    if robust_count >= total // 2:
        print(">>> Strategy appears ROBUST (most combos work).")
    else:
        print(">>> Strategy likely OVERFIT (only few combos work).")
    # Also show best combo by OOS Sharpe
    if results:
        best = max(results, key=lambda x: x["OOS Sharpe"])
        print(f"\nBest combo: LB={best['lookback']}, TN={best['topN']}, Off={best['offset']} "
              f"→ Sharpe {best['OOS Sharpe']:.2f}, CAGR {best['OOS CAGR']:.1%}, MaxDD {best['OOS maxDD']:.1%}")


def test_month_end_baseline():
    """Test the baseline month-end rebalance with lookback=12, top_N=2 (approx 30% of 8)."""
    print("\n" + "="*80)
    print("BASELINE MONTH-END REBALANCE — Universe B (lookback=12, top_N=2)")
    print("="*80)
    px_daily = daily_data(CROSS)
    lb, tn = 12, 2
    strat_ret = run_xsmom_sweep(px_daily, lb, tn, offset_day=None, month_end=True)
    if strat_ret.empty:
        print("No returns generated.")
        return
    monthly = (1 + strat_ret).resample('ME').prod() - 1
    monthly_list = [(idx, val) for idx, val in monthly.items()]
    IS = stats(monthly_list, 2010, 2021)
    OOS = stats(monthly_list, 2022, 2026)
    if IS is None or OOS is None:
        print("Insufficient data for stats.")
        return
    b = spy_bench(2022, 2026)
    print(f"\nIS  (2010-21): n={IS['n']:3d} wr={IS['wr']:.0%} CAGR={IS['cagr']:+.1%} "
          f"Sharpe={IS['sharpe']:.2f} maxDD={IS['dd']:.1%}")
    print(f"OOS (2022-26): n={OOS['n']:3d} wr={OOS['wr']:.0%} CAGR={OOS['cagr']:+.1%} "
          f"Sharpe={OOS['sharpe']:.2f} maxDD={OOS['dd']:.1%}")
    print(f"  SPY bench OOS : CAGR={b['cagr']:+.1%} Sharpe={b['sharpe']:.2f} maxDD={b['dd']:.1%}")
    checks = {
        "[01] OOS Sharpe>0.5": OOS["sharpe"] > 0.5,
        "[02] maxDD>-35%":     OOS["dd"] > -0.35,
        "[03] OOS Sharpe<2.5": OOS["sharpe"] < 2.5,
        "[04] not overfit":    OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
        "[05] >=30 trades":    OOS["n"] >= 30,
        "[06] IS Sharpe>0":    IS["sharpe"] > 0,
    }
    for k, v in checks.items():
        print(f"    [{'PASS' if v else 'FAIL'}] {k}")
    beats = OOS["sharpe"] > b["sharpe"]
    print(f"  Beats SPY (risk-adj)? {'YES' if beats else 'NO'}")
    print(f"  >>> {'PASSES ALL SIX' if all(checks.values()) else 'REJECTED'}")


# ------------------- Original Universe A & B (default run) -------------------
if __name__ == "__main__":
    # Run original analysis for both universes (as before)
    for nm, univ in [("A) 11 SPDR sectors", SECTORS), ("B) 8 cross-asset sleeves", CROSS)]:
        px = monthly_closes(univ)
        print(f"\n### {nm}: {list(px.columns)} | {px.index.min().date()}→{px.index.max().date()}")
        rets, _ = run_xsmom(px)
        gauntlet(nm, rets)
    # Then run the sensitivity sweep for universe B
    sweep_universe_B()
    # Finally, test month-end baseline to compare with original
    test_month_end_baseline()