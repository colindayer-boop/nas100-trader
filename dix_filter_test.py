"""
dix_filter_test.py — does the SqueezeMetrics DIX (dark-pool buying index)
improve the validated Asian-sweep trades as a DAILY REGIME GATE?

PROP-FIRM NOTE: DIX is a signal INPUT, not an instrument — the account still
trades US100 CFDs exactly as now. Free daily CSV, no options position needed.

Design (A/B on identical trade simulation — approximation biases cancel):
  • Signals: S1 + S4 sweep logic replayed from verify_liveness.py on
    qqq_hourly_7y.csv (on the VPS this is the US100 broker feed alias).
  • Trade sim: enter at signal close, stop −1.5%, target +4.5% (3:1), exit at
    16:00 ET close if neither hit; same-bar stop-first (pessimistic); 4bp cost.
  • Gate uses the PREVIOUS day's DIX (no lookahead). Variants (a-priori, no
    tuning): fixed 45.0 threshold (SqueezeMetrics white paper: >45 = strong
    dark-pool buying) and trailing 252-day median. The INVERSE gate is run as
    a control — if "low DIX" looks as good, the split is noise, not signal.

ADOPTION RULE: gate must IMPROVE OOS Sharpe/PF vs baseline, keep n >= 30 OOS,
and beat its inverse control. Otherwise: FINDINGS graveyard.

Run on the VPS:  python dix_filter_test.py
"""
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from verify_liveness import load_hourly, s1_signals, s4_signals

DIX_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
STOP, RR, COST = 0.015, 3.0, 0.0004
IS_FRAC = 0.6


def get_dix():
    path = "DIX.csv"
    if not os.path.exists(path):
        import requests
        print(f"downloading {DIX_URL} …")
        r = requests.get(DIX_URL, timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
    d = pd.read_csv(path)
    d.columns = [c.strip().lower() for c in d.columns]
    d["date"] = pd.to_datetime(d["date"]).dt.date
    return d.set_index("date")["dix"] * (100 if d["dix"].max() <= 1.0 else 1)


def simulate(data, sig):
    """First signal per day → R-multiple outcome (stop/target/EOD close)."""
    trades = []
    fired = sig[sig]
    seen_days = set()
    for ts in fired.index:
        day = ts.date()
        if day in seen_days:
            continue
        seen_days.add(day)
        entry = float(data.loc[ts, "Close"])
        stop, tgt = entry * (1 - STOP), entry * (1 + STOP * RR)
        rest = data[(data.index > ts) & (data.index.date == day)]
        r = None
        for _, bar in rest.iterrows():
            if bar["Low"] <= stop:                 # pessimistic: stop first
                r = -1.0
                break
            if bar["High"] >= tgt:
                r = RR
                break
        if r is None:
            px = float(rest["Close"].iloc[-1]) if len(rest) else entry
            r = (px - entry) / (entry * STOP)
        trades.append((day, r - COST / STOP))
    return trades


def stats(rs):
    t = pd.Series([r for _, r in rs], dtype=float)
    if len(t) < 2:
        return dict(n=len(t), wr=0, avg=0, sharpe=0, pf=0)
    wins, losses = t[t > 0].sum(), -t[t <= 0].sum()
    return dict(n=len(t), wr=(t > 0).mean(), avg=t.mean(),
                sharpe=t.mean() / t.std() * np.sqrt(len(t)),
                pf=(wins / losses if losses > 0 else np.inf))


def show(label, rs):
    s = stats(rs)
    print(f"  {label:<28} n={s['n']:>4}  wr={s['wr']:.0%}  avgR={s['avg']:+.2f}  "
          f"Sharpe={s['sharpe']:+.2f}  PF={s['pf']:.2f}")
    return s


if __name__ == "__main__":
    dix = get_dix()
    print(f"DIX: {len(dix)} days  ({dix.index.min()} → {dix.index.max()}), "
          f"mean {dix.mean():.1f}")
    data = load_hourly("QQQ")
    sig = s1_signals(data.copy()) | s4_signals(data.copy())
    trades = simulate(data, sig)
    if not trades:
        sys.exit("no trades simulated — check qqq_hourly_7y.csv")
    # previous trading day's DIX for each trade date (no lookahead)
    dix_prev = dix.shift(1)
    med252 = dix.rolling(252).median().shift(1)

    def dix_of(day):
        return dix_prev.get(day, np.nan)

    days = sorted(d for d, _ in trades)
    split = days[int(len(days) * IS_FRAC)]
    print(f"\n{len(trades)} sweep trade-days  ({days[0]} → {days[-1]}), "
          f"IS/OOS split at {split}\n")
    for era, sel in (("IN-SAMPLE", lambda d: d <= split),
                     ("OUT-OF-SAMPLE", lambda d: d > split)):
        sub = [(d, r) for d, r in trades if sel(d)]
        print(f"{era}:")
        base = show("baseline (no gate)", sub)
        hi = show("DIX>45 gate", [(d, r) for d, r in sub if dix_of(d) > 45.0])
        show("DIX<45 (inverse control)", [(d, r) for d, r in sub if dix_of(d) <= 45.0])
        show("DIX>252d-median gate",
             [(d, r) for d, r in sub
              if not np.isnan(med252.get(d, np.nan)) and dix_of(d) > med252.get(d)])
        print()
    print("ADOPTION RULE: a gate earns a slot ONLY if OOS Sharpe and PF beat the")
    print("baseline, n stays >= 30, AND the inverse control is clearly worse.")
    print("If gate ≈ inverse, the DIX split is noise → log REJECTED in FINDINGS.")
