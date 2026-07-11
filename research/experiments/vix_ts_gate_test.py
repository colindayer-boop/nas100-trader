"""EXP-20260711-01: VIX term-structure regime gate on S1 + S5 (isolated research).

Variants (a-priori, from the idea note -- ALL reported, no cherry-pick):
  A baseline        no VIX gate (other filters intact)
  B level gate      current live rule: vix21ma>25 -> 0, >=20 -> 0.5, else 1
  C term-structure  VIX3M/VIX > 1.0 -> 1 (contango), else 0 (backwardation pause)
  D both            min(B, C)

Engine = full_yearly's run_intraday semantics (one entry/day, stop/target,
3 bps/side). Data: qqq_hourly_7y.csv + fresh Alpaca splice; ^VIX/^VIX3M yfinance.
Never touches production. Output: research/results/vix_term_structure_gate.md
"""
import os, sys, warnings
import numpy as np, pandas as pd, pytz
warnings.filterwarnings("ignore")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
eastern = pytz.timezone("US/Eastern")
SLIP = 0.0003

# ---------- data ----------
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
print(f"VIX3M coverage: {min(ratio.index)} -> {max(ratio.index)} ({len(ratio)}d) | "
      f"backwardation days: {(ratio < 1).mean():.1%}")

def mult_level(d):
    v = vma.get(d, np.nan)
    return 1.0 if pd.isna(v) else (0.0 if v > 25 else (0.5 if v >= 20 else 1.0))
def mult_ts(d):
    r = ratio.get(d, np.nan)
    return 1.0 if pd.isna(r) else (1.0 if r > 1.0 else 0.0)
GATES = {"A_baseline": lambda d: 1.0, "B_level": mult_level,
         "C_termstruct": mult_ts, "D_both": lambda d: min(mult_level(d), mult_ts(d))}

# ---------- features (exact full_yearly definitions) ----------
q["Date"] = q.index.date
q["SD"] = q.index.map(lambda i: (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date())
ab = q[q.index.map(lambda i: i.hour >= 18 or i.hour < 2)]
q["AL"] = q["SD"].map(ab.groupby("SD")["Low"].min())
q["InS"] = q.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
tp = (q["High"] + q["Low"] + q["Close"]) / 3
vv, ct, cv, p_ = [], 0.0, 0.0, None
for i in range(len(q)):
    d = q["Date"].iloc[i]
    if d != p_: ct = cv = 0.0; p_ = d
    vol = q["Volume"].iloc[i]
    if vol > 0: ct += tp.iloc[i] * vol; cv += vol
    vv.append(ct / cv if cv > 0 else np.nan)
q["VWAP"] = vv
dc = q[q.index.hour == 16][["Close"]].copy(); dc.index = dc.index.date
dc = dc[~dc.index.duplicated(keep="last")]
q["EMA50"] = q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
pc = q["Close"].shift(1)
tr = pd.concat([q["High"]-q["Low"], (q["High"]-pc).abs(), (q["Low"]-pc).abs()], axis=1).max(axis=1)
atr = tr.rolling(14).mean(); q["HV"] = atr > 1.5 * atr.rolling(200).mean()
q["S1"] = ((q["Low"] < q["AL"]) & (q["Close"] > q["AL"]) & q["InS"] & (q["Close"] > q["VWAP"])
           & (q["Close"] > q["EMA50"]) & ~q["HV"] & q["AL"].notna()).astype(int)
orb = q[q.index.hour == 9]
q["OH"] = q["Date"].map({d: h for d, h in zip(orb["Date"], orb["High"])})
q["OV"] = q["Date"].map({d: v for d, v in zip(orb["Date"], orb["Volume"])})
q["S5"] = (q.index.map(lambda x: 10 <= x.hour <= 13) & (q["Close"] > q["OH"])
           & q["OH"].notna() & (q["Volume"] > q["OV"] * 0.6)).astype(int)

# ---------- engine (full_yearly run_intraday, gate-parameterized) ----------
def run(sig_col, risk, sl, rr, gate):
    cap = 10_000.0; in_t = False; entry = stop = tgt = sh = 0.0
    day_traded = None; trades = 0; daily_eq = {}
    sig = q[sig_col].values; close = q["Close"].values
    dates = q["Date"].values; idx = q.index
    for i in range(1, len(q)):
        price = close[i]; d = dates[i]
        if in_t:
            if price <= stop: cap += sh*(stop-entry) - sh*(entry+stop)*SLIP; in_t = False
            elif price >= tgt: cap += sh*(tgt-entry) - sh*(entry+tgt)*SLIP; in_t = False
        elif sig[i-1] == 1 and day_traded != d:
            vm = gate(dates[i-1])
            if vm > 0:
                in_t = True; day_traded = d; entry = price; trades += 1
                stop = price*(1-sl); tgt = price*(1+sl*rr)
                sh = (cap*risk*vm)/(price*sl)
        daily_eq[d] = cap
    eq = pd.Series(daily_eq).sort_index()
    ret = eq.pct_change().dropna()
    yrs = len(eq)/252
    return {"eq": eq, "ret": ret, "trades": trades,
            "CAGR": (eq.iloc[-1]/eq.iloc[0])**(1/yrs)-1,
            "Sharpe": ret.mean()/ret.std()*np.sqrt(252) if ret.std() > 0 else 0,
            "MaxDD": (eq/eq.cummax()-1).min(), "turnover": trades/yrs}

STRATS = {"S1": ("S1", 0.007, 0.015, 3.0), "S5": ("S5", 0.0075, 0.010, 3.0)}
results = {}
for sname, (col, risk, sl, rr) in STRATS.items():
    for gname, gate in GATES.items():
        results[(sname, gname)] = run(col, risk, sl, rr, gate)

# robustness: OOS Sharpe across 6 split points, per variant
def oos_sharpe(ret, frac):
    o = ret.iloc[int(len(ret)*frac):]
    return o.mean()/o.std()*np.sqrt(252) if o.std() > 0 else 0
SPLITS = [0.45, 0.5, 0.55, 0.6, 0.65, 0.7]
rob = {k: [oos_sharpe(v["ret"], f) for f in SPLITS] for k, v in results.items()}

# ---------- report ----------
out = [f"# EXP-20260711-01 — VIX term-structure regime gate (S1 + S5)",
       f"\n_Generated by research/experiments/vix_ts_gate_test.py. Window: "
       f"{q.index.min().date()} -> {q.index.max().date()}. VIX3M/VIX coverage "
       f"{min(ratio.index)}+, backwardation on {(ratio<1).mean():.1%} of days. "
       f"Costs 3 bps/side. One entry/day. ALL variants reported._\n"]
for sname in STRATS:
    out.append(f"\n## {sname}\n")
    out.append("| variant | CAGR | Sharpe | MaxDD | trades | turnover/yr | OOS Sharpe by split (6) | OOS>B count |")
    out.append("|---|---|---|---|---|---|---|---|")
    base_rob = rob[(sname, "B_level")]
    for g in GATES:
        r = results[(sname, g)]; rb = rob[(sname, g)]
        beats = sum(1 for a, b in zip(rb, base_rob) if a > b)
        out.append(f"| {g} | {r['CAGR']:+.1%} | {r['Sharpe']:.2f} | {r['MaxDD']:.1%} | "
                   f"{r['trades']} | {r['turnover']:.0f} | "
                   f"{' '.join(f'{x:.2f}' for x in rb)} | {beats}/6 |")
out.append("\n## Verdict inputs\n")
for sname in STRATS:
    b = results[(sname, 'B_level')]; c = results[(sname, 'C_termstruct')]; d = results[(sname, 'D_both')]
    out.append(f"- **{sname}**: level-gate Sharpe {b['Sharpe']:.2f} vs term-structure "
               f"{c['Sharpe']:.2f} vs both {d['Sharpe']:.2f}; incremental (D-B) = "
               f"{d['Sharpe']-b['Sharpe']:+.2f}")
out.append("\nDecision rule (from the idea note): the term-structure gate must beat the\n"
           "EXISTING level gate incrementally and consistently across splits, else reject.")
path = os.path.join(REPO, "research", "results", "vix_term_structure_gate.md")
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w").write("\n".join(out) + "\n")
print("\n".join(out[3:]))
print(f"\nwrote {os.path.relpath(path, REPO)}")
