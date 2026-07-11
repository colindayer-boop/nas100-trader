"""EXP-20260711-01 ADVERSARIAL REVIEW (independent reviewer).

Attack vectors:
  R1 look-ahead: original used SAME-DAY closing VIX/VIX3M to gate intraday
     entries. Rerun with PREVIOUS trading day's values (information actually
     available at the decision timestamp). Decisive test.
  R2 blocked-trade counts per variant.
  R3 episode attribution: per-year P&L; leave-out COVID (2020H1), 2022, best yr.
  R4 costs 3 vs 6 bps/side -- does the ranking survive?
  R5 threshold sensitivity 0.95/1.05 (diagnostic only, lagged gating).
  R6 split independence commentary (nested OOS tails).
Engine identical to the experiment otherwise. Research-only.
"""
import os, sys, warnings
import numpy as np, pandas as pd, pytz
warnings.filterwarnings("ignore")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
eastern = pytz.timezone("US/Eastern")

df = pd.read_csv(os.path.join(REPO, "qqq_hourly_7y.csv"))
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
q = df[df["symbol"] == "QQQ"].set_index("timestamp").tz_convert(eastern)[
    ["open", "high", "low", "close", "volume"]]
q.columns = ["Open", "High", "Low", "Close", "Volume"]
try:
    from alpaca_broker import AlpacaBroker
    fresh = AlpacaBroker().get_bars("QQQ", "1Hour", 1200)
    q = pd.concat([q, fresh[fresh.index > q.index.max()]])
except Exception as e:
    print(f"(no splice: {e})")

import yfinance as yf
def daily(t):
    s = yf.download(t, start="2018-06-01", progress=False)["Close"]
    if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).date
    return s
vix, vix3m = daily("^VIX"), daily("^VIX3M")
vma = pd.Series(vix).rolling(21).mean()
ratio = (vix3m / vix).dropna()

# lagged (information-correct) lookups: value from the PREVIOUS trading day
def lag_map(s):
    sh = pd.Series(s).shift(1)
    return sh
vma_lag, ratio_lag = lag_map(vma), lag_map(ratio)

def make_gates(vma_s, ratio_s, thr=1.0):
    def lvl(d):
        v = vma_s.get(d, np.nan)
        return 1.0 if pd.isna(v) else (0.0 if v > 25 else (0.5 if v >= 20 else 1.0))
    def ts(d):
        r = ratio_s.get(d, np.nan)
        return 1.0 if pd.isna(r) else (1.0 if r > thr else 0.0)
    return {"A_nogate": lambda d: 1.0, "B_level": lvl, "C_ts": ts,
            "D_both": lambda d: min(lvl(d), ts(d))}

# ---- features: S5 only (the claim under review) ----
q["Date"] = q.index.date
orb = q[q.index.hour == 9]
q["OH"] = q["Date"].map({d: h for d, h in zip(orb["Date"], orb["High"])})
q["OV"] = q["Date"].map({d: v for d, v in zip(orb["Date"], orb["Volume"])})
q["S5"] = (q.index.map(lambda x: 10 <= x.hour <= 13) & (q["Close"] > q["OH"])
           & q["OH"].notna() & (q["Volume"] > q["OV"] * 0.6)).astype(int)

def run(gate, slip=0.0003, mask=None):
    cap = 10_000.0; in_t = False; entry = stop = tgt = sh = 0.0
    day_traded = None; trades = 0; blocked = 0; daily_eq = {}
    sig = q["S5"].values; close = q["Close"].values; dates = q["Date"].values
    RISK, SL, RR = 0.0075, 0.010, 3.0
    for i in range(1, len(q)):
        d = dates[i]
        if mask is not None and not mask(d):
            if not in_t: daily_eq[d] = cap
            continue
        price = close[i]
        if in_t:
            if price <= stop: cap += sh*(stop-entry) - sh*(entry+stop)*slip; in_t = False
            elif price >= tgt: cap += sh*(tgt-entry) - sh*(entry+tgt)*slip; in_t = False
        elif sig[i-1] == 1 and day_traded != d:
            vm = gate(dates[i-1])
            if vm > 0:
                in_t = True; day_traded = d; entry = price; trades += 1
                stop = price*(1-SL); tgt = price*(1+SL*RR)
                sh = (cap*RISK*vm)/(price*SL)
            else:
                blocked += 1; day_traded = d   # gate consumed the day's entry
        daily_eq[d] = cap
    eq = pd.Series(daily_eq).sort_index(); ret = eq.pct_change().dropna()
    yrs = max(len(eq)/252, 1e-9)
    return {"eq": eq, "ret": ret, "trades": trades, "blocked": blocked,
            "CAGR": (eq.iloc[-1]/eq.iloc[0])**(1/yrs)-1,
            "Sharpe": ret.mean()/ret.std()*np.sqrt(252) if ret.std() > 0 else 0,
            "MaxDD": (eq/eq.cummax()-1).min()}

def sharpe_tail(ret, frac):
    o = ret.iloc[int(len(ret)*frac):]
    return o.mean()/o.std()*np.sqrt(252) if o.std() > 0 else 0
SPLITS = [0.45, 0.5, 0.55, 0.6, 0.65, 0.7]

def table(gates, slip=0.0003, mask=None, label=""):
    rows = {}
    for g, fn in gates.items():
        rows[g] = run(fn, slip=slip, mask=mask)
    print(f"\n--- {label} ---")
    print(f"{'variant':10} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7} {'trades':>7} {'blocked':>8} "
          f"{'OOS Sharpe x6':>34} {'C>B':>4}")
    rb = [sharpe_tail(rows['B_level']['ret'], f) for f in SPLITS]
    for g, r in rows.items():
        rs = [sharpe_tail(r['ret'], f) for f in SPLITS]
        beats = sum(1 for a, b in zip(rs, rb) if a > b)
        print(f"{g:10} {r['CAGR']:>+7.1%} {r['Sharpe']:>7.2f} {r['MaxDD']:>7.1%} "
              f"{r['trades']:>7} {r['blocked']:>8} {' '.join(f'{x:5.2f}' for x in rs):>34} {beats:>3}/6")
    return rows

print("R1 -- LOOK-AHEAD TEST")
same_day = table(make_gates(vma, ratio), label="original: SAME-DAY close gating (as the experiment ran)")
lagged   = table(make_gates(vma_lag, ratio_lag), label="corrected: PREV-DAY close gating (information-correct)")

print("\nR3 -- yearly P&L attribution (lagged gating)")
gates_l = make_gates(vma_lag, ratio_lag)
yr_rows = {}
for g, fn in gates_l.items():
    r = run(fn); e = r["eq"]; e.index = pd.to_datetime(e.index)
    yr_rows[g] = e.resample("YE").last().pct_change().dropna()
yrs_idx = yr_rows["A_nogate"].index.year
print("variant   " + " ".join(f"{y:>7}" for y in yrs_idx))
for g, s in yr_rows.items():
    print(f"{g:10}" + " ".join(f"{v:>+7.1%}" for v in s.values))

print("\nR3 -- leave-one-stress-episode-out (lagged gating)")
def mk_mask(lo=None, hi=None, year=None):
    def m(d):
        if year and d.year == year: return False
        if lo and hi and lo <= d <= hi: return False
        return True
    return m
import datetime as dt
best_year = int(yr_rows["C_ts"].idxmax().year)
for label, mask in [("ex-COVID (2020-02-15..2020-06-30)", mk_mask(dt.date(2020,2,15), dt.date(2020,6,30))),
                    ("ex-2022", mk_mask(year=2022)),
                    (f"ex-best-year ({best_year})", mk_mask(year=best_year))]:
    table(gates_l, mask=mask, label=label)

print("\nR4 -- realistic costs: 6 bps/side (lagged)")
table(gates_l, slip=0.0006, label="6 bps/side")

print("\nR5 -- threshold sensitivity (diagnostic only, lagged): 0.95 / 1.00 / 1.05")
for thr in (0.95, 1.00, 1.05):
    g = make_gates(vma_lag, ratio_lag, thr=thr)
    r = run(g["C_ts"])
    print(f"  thr {thr:.2f}: C_ts Sharpe {r['Sharpe']:.2f} CAGR {r['CAGR']:+.1%} "
          f"DD {r['MaxDD']:.1%} trades {r['trades']} blocked {r['blocked']}")
