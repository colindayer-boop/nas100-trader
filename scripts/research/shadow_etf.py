"""shadow_etf.py -- forward-shadow logger for the reviewed ETF universe.

Once per day (router action or manual), computes TODAY's would-be S1/S5 signals
for every review-surviving stream and appends one row per stream to
research/results/shadow_signals.csv -- signal fired or not, price, and the
shadow regime-gate values (VIX-level gate, VIX3M/VIX term-structure gate).

NO ORDERS. Pure evidence collection for the forward-shadow requirement.
Idempotent: one row per (date, stream); re-runs update nothing if already logged.

Usage: python scripts/research/shadow_etf.py
"""
import csv
import os
import re
import sys
import warnings
from datetime import date

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "research", "results", "shadow_signals.csv")
REVIEW = os.path.join(REPO, "research", "results", "universe_expansion_REVIEW.md")
FIELDS = ["date", "stream", "signal", "price", "gate_vix_level", "gate_ts_ratio",
          "vix21ma", "ts_ratio"]


def survivors():
    """Parse the de-duplicated survivor list from the review artifact."""
    txt = open(REVIEW, encoding="utf-8").read()
    m = re.search(r"de-duplicated set \(\d+\): \[([^\]]+)\]", txt)
    if not m:
        raise SystemExit("no survivor list in universe_expansion_REVIEW.md -- run the review first")
    return [s.strip().strip("'\"") for s in m.group(1).split(",")]


def todays_signals(streams):
    from alpaca_broker import AlpacaBroker
    b = AlpacaBroker()
    out = {}
    syms = sorted({k.split("_")[1] for k in streams})
    for sym in syms:
        q = b.get_bars(sym, "1Hour", 1200)  # match live lookback (starve-proof)
        q["Date"] = q.index.date
        q["SD"] = q.index.map(lambda i: (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date())
        ab = q[q.index.map(lambda i: i.hour >= 18 or i.hour < 2)]
        q["AL"] = q["SD"].map(ab.groupby("SD")["Low"].min())
        q["InS"] = q.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
        tp = (q["High"]+q["Low"]+q["Close"])/3
        vv, ct, cv, p_ = [], 0.0, 0.0, None
        for i in range(len(q)):
            d = q["Date"].iloc[i]
            if d != p_: ct = cv = 0.0; p_ = d
            v = q["Volume"].iloc[i]
            if v > 0: ct += tp.iloc[i]*v; cv += v
            vv.append(ct/cv if cv > 0 else np.nan)
        q["VWAP"] = vv
        dc = q[q.index.hour == 16][["Close"]].copy(); dc.index = dc.index.date
        dc = dc[~dc.index.duplicated(keep="last")]
        q["EMA50"] = q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
        pc = q["Close"].shift(1)
        tr = pd.concat([q["High"]-q["Low"], (q["High"]-pc).abs(), (q["Low"]-pc).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean(); q["HV"] = atr > 1.5*atr.rolling(200).mean()
        s1 = ((q["Low"] < q["AL"]) & (q["Close"] > q["AL"]) & q["InS"] & (q["Close"] > q["VWAP"])
              & (q["Close"] > q["EMA50"]) & ~q["HV"] & q["AL"].notna())
        orb = q[q.index.hour == 9]
        q["OH"] = q["Date"].map({d: h for d, h in zip(orb["Date"], orb["High"])})
        q["OV"] = q["Date"].map({d: v for d, v in zip(orb["Date"], orb["Volume"])})
        s5 = (q.index.map(lambda x: 10 <= x.hour <= 13) & (q["Close"] > q["OH"])
              & q["OH"].notna() & (q["Volume"] > q["OV"]*0.6))
        today = q["Date"].iloc[-1]
        price = float(q["Close"].iloc[-1])
        out[f"S1_{sym}"] = (bool(s1[q["Date"] == today].any()), price)
        out[f"S5_{sym}"] = (bool(pd.Series(s5)[list(q["Date"] == today)].any()), price)
    return {k: out[k] for k in streams if k in out}, str(date.today())


def gates():
    """Shadow gate values from the macro-state dataset (yesterday's close = lag-safe)."""
    p = os.path.join(REPO, "state", "macro_daily.csv")
    if not os.path.exists(p):
        return "", "", "", ""
    m = pd.read_csv(p, index_col=0).iloc[-1]
    lvl = 0.0 if m["vix21ma"] > 25 else (0.5 if m["vix21ma"] >= 20 else 1.0)
    ts = 1.0 if m["ts_ratio"] > 1.0 else 0.0
    return lvl, ts, round(m["vix21ma"], 2), round(m["ts_ratio"], 3)


def main():
    streams = survivors()
    sigs, today = todays_signals(streams)
    lvl, ts, vma, ratio = gates()
    existing = set()
    if os.path.exists(OUT):
        with open(OUT, newline="") as f:
            existing = {(r["date"], r["stream"]) for r in csv.DictReader(f)}
    need_header = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    n = 0
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if need_header:
            w.writeheader()
        for k, (fired, price) in sorted(sigs.items()):
            if (today, k) in existing:
                continue
            w.writerow({"date": today, "stream": k, "signal": int(fired),
                        "price": round(price, 2), "gate_vix_level": lvl,
                        "gate_ts_ratio": ts, "vix21ma": vma, "ts_ratio": ratio})
            n += 1
    fired = sum(1 for _, (x, _) in sigs.items() if x)
    print(f"shadow {today}: {n} rows appended ({len(sigs)} streams, {fired} fired) "
          f"| gates: level={lvl} ts={ts}")


if __name__ == "__main__":
    main()
