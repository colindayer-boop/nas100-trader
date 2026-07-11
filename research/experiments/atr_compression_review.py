"""ADVERSARIAL REVIEW: 'ATR compression filter' claim (volatility_regime_report.md:
'compressed_only Sharpe 2.04 vs baseline 1.12' on S1, compressed = atr_pctl<0.25).

Falsification battery per mission: rolling walk-forward, 8 thresholds (report ALL,
0.25 was chosen post-hoc), trade counts, interaction with VIX/TS/HighVol/GEX gates,
incremental information beyond existing filters, leave-one-year-out, 2x costs.
Research only. Verdict at the end.
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
except Exception:
    pass

# ---- S1 features (exact) ----
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
dc = q[q.index.hour == 16][["Close", "High", "Low"]].copy() if False else q[q.index.hour == 16][["Close"]].copy()
dc.index = dc.index.date; dc = dc[~dc.index.duplicated(keep="last")]
q["EMA50"] = q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
pc = q["Close"].shift(1)
tr = pd.concat([q["High"]-q["Low"], (q["High"]-pc).abs(), (q["Low"]-pc).abs()], axis=1).max(axis=1)
atr_h = tr.rolling(14).mean()
q["HV"] = atr_h > 1.5*atr_h.rolling(200).mean()
q["S1"] = ((q["Low"] < q["AL"]) & (q["Close"] > q["AL"]) & q["InS"] & (q["Close"] > q["VWAP"])
           & (q["Close"] > q["EMA50"]) & ~q["HV"] & q["AL"].notna()).astype(int)

# ---- daily ATR percentile (their definition: daily ATR14 pct-rank over 252d) ----
day = q.groupby("Date").agg(H=("High", "max"), L=("Low", "min"), C=("Close", "last"))
day.index = pd.to_datetime(day.index)
pcd = day["C"].shift(1)
trd = pd.concat([day["H"]-day["L"], (day["H"]-pcd).abs(), (day["L"]-pcd).abs()], axis=1).max(axis=1)
atr_d = trd.rolling(14).mean()
atr_pctl = atr_d.rolling(252).rank(pct=True).shift(1)   # LAGGED: yesterday's percentile
atr_map = {d.date(): v for d, v in atr_pctl.items()}

# ---- gates (lagged) ----
import yfinance as yf
def yfd(t):
    s = yf.download(t, start="2018-06-01", progress=False)["Close"]
    if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).date
    return s
vix = yfd("^VIX"); vix3m = yfd("^VIX3M")
vma = pd.Series(vix).rolling(21).mean().shift(1)
ts_ratio = (vix3m/vix).shift(1)
gex = pd.read_csv(os.path.join(REPO, "gex_history.csv"), index_col=0)
gex.index = pd.to_datetime(gex.index).date
gex_neg = {d: (v < 0) for d, v in (gex["gex"] if "gex" in gex.columns else gex.iloc[:, 0]).items()}

def run(filt=None, slip=0.0003, years_excl=(), date_lo=None, date_hi=None):
    cap = 10_000.0; in_t = False; entry = stop = tgt = sh = 0.0
    day_traded = None; trades = 0; daily_eq = {}
    sig = q["S1"].values; close = q["Close"].values; dates = q["Date"].values
    RISK, SL, RR = 0.007, 0.015, 3.0
    for i in range(1, len(q)):
        d = dates[i]
        if d.year in years_excl or (date_lo and d < date_lo) or (date_hi and d >= date_hi):
            if not in_t: daily_eq[d] = cap
            continue
        price = close[i]
        if in_t:
            if price <= stop: cap += sh*(stop-entry)-sh*(entry+stop)*slip; in_t = False
            elif price >= tgt: cap += sh*(tgt-entry)-sh*(entry+tgt)*slip; in_t = False
        elif sig[i-1] == 1 and day_traded != d:
            if filt is None or filt(dates[i-1]):
                in_t = True; day_traded = d; entry = price; trades += 1
                stop = price*(1-SL); tgt = price*(1+SL*RR); sh = (cap*RISK)/(price*SL)
            else:
                day_traded = d
        daily_eq[d] = cap
    eq = pd.Series(daily_eq).sort_index(); ret = eq.pct_change().dropna()
    return {"ret": ret, "trades": trades,
            "Sharpe": ret.mean()/ret.std()*np.sqrt(252) if ret.std() > 0 else 0}

def shp(x):
    x = x.dropna()
    return x.mean()/x.std()*np.sqrt(252) if len(x) > 40 and x.std() > 0 else np.nan

def comp_filter(thr):
    return lambda d: (atr_map.get(d) is not None and atr_map[d] < thr)

out = ["# ADVERSARIAL REVIEW — 'ATR compression filter' (claim: S1 compressed_only 2.04 vs 1.12)",
       "\n_All thresholds reported (0.25 was selected post-hoc by the original analysis;",
       "its report simultaneously found compression is NOT a breakout signal, ratio 0.83x).",
       "atr_pctl LAGGED one day here (original used same-day). Base engine = validated S1._\n"]

base = run()
out.append(f"Baseline S1 (no compression filter): Sharpe {base['Sharpe']:.2f}, trades {base['trades']}\n")
out.append("## T2/T3 — threshold sweep + trade counts (full sample, 3 bps)")
out.append("| threshold pctl | Sharpe | trades | trades kept % |")
out.append("|---|---|---|---|")
sweep = {}
for thr in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
    r = run(comp_filter(thr)); sweep[thr] = r
    out.append(f"| <{thr:.0%} | {r['Sharpe']:.2f} | {r['trades']} | {r['trades']/max(base['trades'],1):.0%} |")

out.append("\n## T1 — rolling walk-forward (expanding 6 tail-splits), compressed<0.25 vs baseline")
out.append("| split | base OOS | filt OOS |")
out.append("|---|---|---|")
wins = 0
for f in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7):
    b = shp(base["ret"].iloc[int(len(base['ret'])*f):])
    c = shp(sweep[0.25]["ret"].iloc[int(len(sweep[0.25]['ret'])*f):])
    wins += int(c > b)
    out.append(f"| {f:.2f} | {b:.2f} | {c:.2f} |")
out.append(f"filter beats baseline on {wins}/6 splits")

out.append("\n## T4/T5 — interaction & incremental information (Sharpe after existing gates, 3 bps)")
def lvl_gate(d): v = vma.get(d, np.nan); return not (not pd.isna(v) and v >= 20)
def ts_gate(d): r = ts_ratio.get(d, np.nan); return pd.isna(r) or r > 1.0
def gex_gate(d): return gex_neg.get(d, True)
combos = {
    "VIX level gate only": lvl_gate,
    "VIX + compression<0.25": lambda d: lvl_gate(d) and comp_filter(0.25)(d),
    "TS gate only": ts_gate,
    "TS + compression<0.25": lambda d: ts_gate(d) and comp_filter(0.25)(d),
    "GEX gate only (to 2023-12)": gex_gate,
    "GEX + compression (to 2023-12)": lambda d: gex_gate(d) and comp_filter(0.25)(d),
}
import datetime as dt
out.append("| combo | Sharpe | trades |")
out.append("|---|---|---|")
for name, f in combos.items():
    hi = dt.date(2024, 1, 1) if "2023-12" in name else None
    r = run(f, date_hi=hi)
    out.append(f"| {name} | {r['Sharpe']:.2f} | {r['trades']} |")
out.append("(HighVol gate is already inside S1 -- compression is tested on top of it by construction.)")

out.append("\n## T6 — leave-one-year-out (compressed<0.25 minus baseline Sharpe)")
out.append("| excluded year | base | filt | delta |")
out.append("|---|---|---|---|")
deltas = []
for y in range(2019, 2027):
    b = run(years_excl=(y,)); c = run(comp_filter(0.25), years_excl=(y,))
    deltas.append(c["Sharpe"]-b["Sharpe"])
    out.append(f"| {y} | {b['Sharpe']:.2f} | {c['Sharpe']:.2f} | {c['Sharpe']-b['Sharpe']:+.2f} |")

out.append("\n## T7 — doubled costs (6 bps/side), compressed<0.25 vs baseline")
b6 = run(slip=0.0006); c6 = run(comp_filter(0.25), slip=0.0006)
out.append(f"baseline {b6['Sharpe']:.2f} ({b6['trades']} tr) vs filtered {c6['Sharpe']:.2f} ({c6['trades']} tr)")

path = os.path.join(REPO, "research", "results", "atr_compression_REVIEW.md")
open(path, "w").write("\n".join(out) + "\n")
print("\n".join(out))
