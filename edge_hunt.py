"""
edge_hunt.py — Autonomous overnight edge miner. Runs a battery of A-PRIORI edge
candidates through the SAME gauntlet the live book was held to, and logs every
result (pass or fail) to HUNT_LOG.md. Designed to reject almost everything — a
night that honestly rejects 15 ideas is a success.

Discipline (see EDGE_HUNT_BRIEF.md):
  - a-priori params only (no grid-search-then-report-best)
  - IS/OOS walk-forward split, costs ON
  - must clear: OOS Sharpe>0.5, |corr to QQQ|<0.3, IS Sharpe>0, OOS DD>-35%,
    not-overfit (OOS<=IS*1.3+0.5), >=30 OOS trades/obs, works in a bear sub-period

Usage:
    python edge_hunt.py --all              # run every candidate once
    python edge_hunt.py --all --loop       # run all night: re-run on fresh data,
                                           #   also perturbs IS/OOS split to test robustness
    python edge_hunt.py --edge turn_of_month
"""
import argparse, time, warnings
from datetime import date
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

LOG = "HUNT_LOG.md"
_PX_CACHE = {}


def px(tkr, start="2007-01-01", interval="1d"):
    """Download adjusted OHLCV. Cached per (tkr, start, interval): overnight the
    daily bars are static, so re-fetching 12x/round only invites yfinance throttling
    (the empty/ERR rows). Cache once, reuse everywhere."""
    key = (tkr, start, interval)
    if key in _PX_CACHE:
        return _PX_CACHE[key]
    import yfinance as yf
    d = yf.download(tkr, start=start, end=str(date.today()), interval=interval,
                    progress=False, auto_adjust=True)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    if d is None or d.empty:
        raise ValueError(f"no data for {tkr!r} (yfinance returned empty — likely throttled)")
    _PX_CACHE[key] = d
    return d


def _qqq_daily():
    q = px("QQQ")["Close"]
    return q.pct_change()


def _periods_per_year(idx):
    """Infer *actual* observations-per-year so Sharpe is annualized correctly whether the
    series is daily, weekly or monthly (not hardcoded 252). Counts real bars over the true
    calendar span — trading-daily lands at ~252 (median spacing would wrongly say 365,
    since business days are 1 calendar day apart), monthly at ~12, weekly at ~52."""
    if len(idx) < 3:
        return 252.0
    span_days = (idx[-1] - idx[0]).days
    if span_days <= 0:
        return 252.0
    return float(np.clip(len(idx) / (span_days / 365.25), 1.0, 365.0))


def gauntlet(name, daily_ret, split=0.6, cost_bps=4, min_obs=30):
    """daily_ret: pd.Series of strategy returns (net of position). Returns dict."""
    s = daily_ret.dropna()
    if len(s) < min_obs * 2:
        return dict(name=name, verdict="FAIL", why=f"too few obs ({len(s)})")
    cut = s.index[int(len(s) * split)]
    IS, OOS = s[s.index < cut], s[s.index >= cut]

    ppy = _periods_per_year(s.index)

    def sharpe(x): return x.mean() / x.std() * np.sqrt(ppy) if x.std() > 0 else 0
    def dd(x): eq = (1 + x).cumprod(); return (eq / eq.cummax() - 1).min()

    iss, oss = sharpe(IS), sharpe(OOS)
    oos_dd = dd(OOS)
    # correlation to QQQ, resampled to match the strategy's own frequency (weekly for
    # daily strats, monthly for coarser ones) — mixing daily QQQ with a monthly series
    # would flood the join with zero-weeks and understate |corr|.
    q = _qqq_daily()
    rule = "W" if ppy > 60 else "ME"
    j = pd.DataFrame({"s": s, "q": q}).dropna()
    per = j.resample(rule).sum()
    corr = per["s"].corr(per["q"]) if len(per) > 5 else 1.0
    # bear sub-period (2022) must not be deeply negative
    bear = s[(s.index >= "2022-01-01") & (s.index < "2023-01-01")]
    bear_ok = (bear.sum() > -0.10) if len(bear) > 20 else True
    n_oos = (OOS != 0).sum()

    checks = {
        "OOS Sharpe>0.5": oss > 0.5,
        "IS Sharpe>0": iss > 0,
        "OOS DD>-35%": oos_dd > -0.35,
        "not overfit": oss <= iss * 1.3 + 0.5,
        ">=30 OOS obs": n_oos >= min_obs,
        "|corr QQQ|<0.3": abs(corr) < 0.3,
        "bear ok": bear_ok,
    }
    passed = all(checks.values())
    fails = [k for k, v in checks.items() if not v]
    # prop-fitness: at fixed vol-target, pass-speed scales with Sharpe (timeout fix);
    # steadiness (% positive months) protects the consistency rule. Rank passes by both.
    monthly = OOS.resample("ME").sum()
    pos_months = (monthly > 0).mean() if len(monthly) else 0
    cagr = (1 + OOS).prod() ** (ppy / max(len(OOS), 1)) - 1
    prop_fit = round(max(oss, 0) * pos_months, 2)
    return dict(name=name, verdict="PASS" if passed else "FAIL",
                IS=round(iss, 2), OOS=round(oss, 2), dd=round(oos_dd, 3),
                corr=round(corr, 2), n=int(n_oos), cagr=round(cagr, 3),
                posm=round(pos_months, 2), pf=prop_fit,
                why="all clear" if passed else "; ".join(fails))


# ── CANDIDATE EDGES (a-priori, free daily data) ─────────────────────────────
def turn_of_month():
    """Long SPY last 1 + first 3 trading days of month, flat else. Calendar anomaly."""
    c = px("SPY")["Close"]; r = c.pct_change()
    dom = c.index.to_series().groupby([c.index.year, c.index.month])
    pos = pd.Series(0.0, index=c.index)
    for _, idx in dom:
        pos.loc[idx[:3]] = 1.0          # first 3 days
        pos.loc[idx[-1:]] = 1.0         # last day
    return (pos.shift(1) * r - pos.diff().abs().fillna(0) * 0.0004).dropna()


def _pairs(sa, sb, lookback=60, cost=0.0008, start="2007-01-01"):
    """Generic z-score mean-reversion on a cointegrated pair. Market-neutral,
    STEADY returns -> consistency-rule friendly (no single lumpy day)."""
    a = px(sa, start)["Close"]; b = px(sb, start)["Close"]
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    ra, rb = df["a"].pct_change(), df["b"].pct_change()
    spread = np.log(df["a"]) - np.log(df["b"])
    z = (spread - spread.rolling(lookback).mean()) / spread.rolling(lookback).std()
    pos = (-z.clip(-2, 2) / 2).shift(1)           # long a/short b when spread low
    return (pos * (ra - rb) - pos.diff().abs().fillna(0) * cost).dropna()


def pairs_gld_gdx():  return _pairs("GLD", "GDX")     # gold vs miners
def pairs_xle_xop():  return _pairs("XLE", "XOP")     # energy sector vs producers
def pairs_ewa_ewc():  return _pairs("EWA", "EWC")     # Australia vs Canada (commodity betas)
def pairs_ko_pep():   return _pairs("KO", "PEP")      # classic consumer-staples pair
def pairs_gld_tlt():  return _pairs("GLD", "TLT")     # gold vs long bonds (real-rate proxy)


def rsi2_spy():
    """Connors RSI-2 mean-reversion, long-only above 200SMA. High-frequency, STEADY
    daily P&L -> ideal for the consistency rule; accrues target fast (timeout fix)."""
    c = px("SPY")["Close"]; r = c.pct_change()
    d = c.diff(); up = d.clip(lower=0).rolling(2).mean(); dn = (-d.clip(upper=0)).rolling(2).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    sma = c.rolling(200).mean()
    rv, cv, sv = rsi.values, c.values, sma.values
    state = 0; arr = []
    for i in range(len(c)):
        if state == 0 and rv[i] < 10 and cv[i] > sv[i]: state = 1
        elif state == 1 and rv[i] > 60: state = 0
        arr.append(state)
    pos = pd.Series(arr, index=c.index, dtype=float)
    return (pos.shift(1) * r - pos.diff().abs().fillna(0) * 0.0004).dropna()


def tsmom_spy():
    """12-1 month time-series momentum on SPY (canonical trend). Long/short."""
    c = px("SPY")["Close"]; r = c.pct_change()
    m = c.shift(21) / c.shift(252) - 1
    pos = np.sign(m).shift(1)
    return (pos * r - pos.diff().abs().fillna(0) * 0.0004).dropna()


def short_reversal_qqq():
    """5-day short-term reversal on QQQ (bet against the last week). Steady, frequent."""
    c = px("QQQ")["Close"]; r = c.pct_change()
    pos = (-np.sign(c.pct_change(5)) * 0.5).shift(1)
    return (pos * r - pos.diff().abs().fillna(0) * 0.0004).dropna()


def crypto_weekend():
    """BTC weekend effect: hold Fri close -> Mon, flat weekdays. Free daily."""
    c = px("BTC-USD", "2015-01-01")["Close"]; r = c.pct_change()
    pos = pd.Series(0.0, index=c.index)
    pos[c.index.dayofweek == 4] = 1.0             # enter Friday
    ret = pos.shift(1) * r - pos.diff().abs().fillna(0) * 0.001
    return ret.dropna()


def defensive_rotation():
    """Long SPLV (low-vol) minus SPY when VIX elevated; market-relative defensive edge."""
    lv = px("SPLV", "2011-01-01")["Close"]; sp = px("SPY", "2011-01-01")["Close"]
    vix = px("^VIX", "2011-01-01")["Close"]
    df = pd.DataFrame({"lv": lv.pct_change(), "sp": sp.pct_change(), "vix": vix}).dropna()
    hi = df["vix"] > df["vix"].rolling(60).median()
    pos = hi.astype(float).shift(1)               # tilt to low-vol when vix high
    return (pos * (df["lv"] - df["sp"])).dropna()


def sector_momentum():
    """Cross-sectional: long top-2 / short bottom-2 sector ETFs by 3mo return, monthly."""
    etfs = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLI", "XLP", "XLU", "XLB"]
    cl = pd.DataFrame({e: px(e, "2007-01-01")["Close"] for e in etfs}).dropna()
    mret = cl.resample("ME").last().pct_change()
    mom = cl.resample("ME").last().pct_change(3)
    out = []
    for i in range(4, len(mom) - 1):
        rank = mom.iloc[i].rank()
        longs = rank.nlargest(2).index; shorts = rank.nsmallest(2).index
        r = mret.iloc[i + 1][longs].mean() - mret.iloc[i + 1][shorts].mean()
        out.append((mret.index[i + 1], r - 0.001))
    # keep the native MONTHLY frequency — zero-filling to a daily calendar corrupted the
    # std (mostly-zero days) and made the annualized Sharpe meaningless. gauntlet infers
    # the frequency and annualizes by sqrt(~12) correctly.
    return pd.Series(dict(out)).sort_index()


CANDIDATES = {
    "turn_of_month": turn_of_month,
    "pairs_gld_gdx": pairs_gld_gdx,
    "pairs_xle_xop": pairs_xle_xop,
    "pairs_ewa_ewc": pairs_ewa_ewc,
    "pairs_ko_pep": pairs_ko_pep,
    "pairs_gld_tlt": pairs_gld_tlt,
    "rsi2_spy": rsi2_spy,
    "tsmom_spy": tsmom_spy,
    "short_reversal_qqq": short_reversal_qqq,
    "crypto_weekend": crypto_weekend,
    "defensive_rotation": defensive_rotation,
    "sector_momentum": sector_momentum,
}


HEADER = ("# HUNT LOG\n\n"
          "prop_fit = OOS Sharpe x %positive-months (higher = passes faster & survives "
          "the consistency rule). Rank PASS rows by prop_fit.\n\n"
          "| when | edge | IS | OOS | OOS_DD | corr | CAGR | pos_mo | prop_fit | n | verdict | why |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|\n")


def logrow(r):
    line = (f"| {time.strftime('%Y-%m-%d %H:%M')} | {r['name']} | {r.get('IS','-')} | "
            f"{r.get('OOS','-')} | {r.get('dd','-')} | {r.get('corr','-')} | "
            f"{r.get('cagr','-')} | {r.get('posm','-')} | {r.get('pf','-')} | "
            f"{r.get('n','-')} | **{r['verdict']}** | {r['why']} |")
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line)


def run_one(key, split=0.6):
    try:
        ret = CANDIDATES[key]()
        r = gauntlet(key, ret, split=split)
    except Exception as e:
        r = dict(name=key, verdict="ERR", why=f"{type(e).__name__}: {e}")
    logrow(r)
    return r


SWEEP_SPLITS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)
SWEEP_OUT = "SWEEP_SUMMARY.md"


def sweep(keys, splits=SWEEP_SPLITS):
    """Evaluate every candidate across a panel of IS/OOS splits in ONE pass (compute the
    return series once, re-split many times) and rank by robustness. A candidate that
    passes 6/6 splits is a real edge; one that flickers 1/6 is split-luck. Writes a ranked
    summary to SWEEP_SUMMARY.md — this is the morning deliverable."""
    rows = []
    for k in keys:
        try:
            ret = CANDIDATES[k]()                       # computed ONCE, reused per split
            res = [gauntlet(k, ret, split=sp) for sp in splits]
        except Exception as e:
            rows.append(dict(name=k, passes=0, n=len(splits), med_oos=None,
                             min_oos=None, med_pf=None, note=f"{type(e).__name__}: {e}"))
            continue
        oos = [r["OOS"] for r in res if "OOS" in r]
        pf = [r["pf"] for r in res if "pf" in r]
        npass = sum(1 for r in res if r["verdict"] == "PASS")
        rows.append(dict(name=k, passes=npass, n=len(splits),
                         med_oos=round(float(np.median(oos)), 2) if oos else None,
                         min_oos=round(min(oos), 2) if oos else None,
                         med_pf=round(float(np.median(pf)), 2) if pf else None,
                         note="robust" if npass == len(splits) else
                              ("split-luck" if 0 < npass < len(splits) else "reject")))
    # rank: most splits passed, then median OOS Sharpe, then prop-fitness
    rows.sort(key=lambda r: (r["passes"], r["med_oos"] or -9, r["med_pf"] or -9), reverse=True)
    hdr = ("# SWEEP SUMMARY\n\n"
           f"Each candidate evaluated across splits {list(splits)}. "
           "`passes` = how many of those splits cleared the full gauntlet. "
           "**6/6 = robust edge; 1-5/6 = split-luck (reject); 0/6 = reject.** "
           "Ranked by robustness, then median OOS Sharpe.\n\n"
           f"_generated {time.strftime('%Y-%m-%d %H:%M')}_\n\n"
           "| edge | passes | med_OOS | min_OOS | med_prop_fit | note |\n"
           "|---|---|---|---|---|---|\n")
    with open(SWEEP_OUT, "w") as f:
        f.write(hdr)
        for r in rows:
            f.write(f"| {r['name']} | {r['passes']}/{r['n']} | {r['med_oos']} | "
                    f"{r['min_oos']} | {r['med_pf']} | {r['note']} |\n")
    print(hdr + "".join(
        f"| {r['name']} | {r['passes']}/{r['n']} | {r['med_oos']} | {r['min_oos']} | "
        f"{r['med_pf']} | {r['note']} |\n" for r in rows))
    print(f"\nwrote {SWEEP_OUT}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge", choices=list(CANDIDATES))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--loop", action="store_true", help="run all night; perturb splits")
    ap.add_argument("--sweep", action="store_true",
                    help="evaluate every candidate across a panel of splits in one pass "
                         "and write a ranked robustness summary (SWEEP_SUMMARY.md)")
    args = ap.parse_args()

    keys = [args.edge] if args.edge else list(CANDIDATES)

    if args.sweep:
        sweep(keys)
        return

    import os
    if not os.path.exists(LOG):
        with open(LOG, "w") as f:
            f.write(HEADER)
    rnd = 0
    while True:
        rnd += 1
        split = 0.6 if not args.loop else float(np.clip(0.5 + 0.1 * np.sin(rnd), 0.45, 0.75))
        print(f"\n--- round {rnd} (IS/OOS split={split:.2f}) ---")
        passes = [run_one(k, split) for k in keys]
        n_pass = sum(1 for p in passes if p["verdict"] == "PASS")
        print(f"round {rnd}: {n_pass}/{len(keys)} passed "
              f"(reject-most is correct — see {LOG})")
        if not args.loop:
            break
        time.sleep(1800)          # re-run every 30 min through the night


if __name__ == "__main__":
    main()
