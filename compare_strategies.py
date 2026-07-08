"""
compare_strategies.py — Side-by-side comparison of the two deployable strategies.

Strategy A: QQQ Asian Sweep system
  S1  — Asian low sweep, any uptrend (EMA50)
  S4  — Same as S1 but also requires EMA50 > EMA200 (stronger regime gate)
  S5L — Hourly ORB long breakout, uptrend regime
  S5S — Hourly ORB short breakout, Faber bear regime
  GLD — Gold FVG long, uptrend regime (uncorrelated diversifier)
  Data: qqq_hourly_7y.csv + gld (yfinance)

Strategy B: BTC Funding Rate Fade
  Signal: extreme funding (>0.05%/8h) → fade the overcrowded side
  Hold: 8h, SL=2%, RR=2×
  Data: data/btcusdt_perp_1m_*.parquet + data/btcusdt_funding.parquet

Comparison window: 2021-2024 (overlapping data for both)
IN-sample: 2021-22 | OUT-of-sample: 2023-24
"""

import io, os, warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import pytz

warnings.filterwarnings("ignore")
eastern  = pytz.timezone("US/Eastern")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

YEARS = [2021, 2022, 2023, 2024]

# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY A — QQQ Asian Sweep system
# ══════════════════════════════════════════════════════════════════════════════
RISK_S1 = 0.0070; STOP_S1 = 0.015; RR_S1 = 3.0
RISK_S4 = 0.0040; STOP_S4 = 0.015; RR_S4 = 3.0
RISK_S5 = 0.0075; STOP_S5 = 0.010; RR_S5 = 3.0
SLIP_QQQ = 0.0003


def load_qqq():
    df = pd.read_csv("qqq_hourly_7y.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").tz_convert(eastern)
    if "symbol" in df.columns:
        df = df[df["symbol"] == "QQQ"]
    df = df[["open","high","low","close","volume"]].copy()
    df.columns = ["Open","High","Low","Close","Volume"]
    df["Date"] = df.index.date
    return df


def build_qqq_signals(q):
    def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
    def sess_date(idx): return (idx + timedelta(days=1)).date() if idx.hour >= 18 else idx.date()

    q["Asian"]       = q.index.map(is_asian)
    q["SessionDate"] = q.index.map(sess_date)
    ab = q[q["Asian"]]
    q["AsianHigh"] = q["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
    q["AsianLow"]  = q["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())

    def in_sess(x):
        h, m = x.hour, x.minute
        return (2<=h<5) or (h==9 and m>=30) or (10<=h<12)
    q["InSession"] = q.index.map(in_sess)

    pc = q["Close"].shift(1)
    tr = pd.concat([q["High"]-q["Low"],(q["High"]-pc).abs(),(q["Low"]-pc).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    q["HighVol"] = atr > 1.5 * atr.rolling(200).mean()

    daily_close = q[q.index.hour == 16][["Close"]].copy()
    daily_close.index = daily_close.index.date
    daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
    ema50  = daily_close["Close"].ewm(span=50).mean()
    ema200 = daily_close["Close"].ewm(span=200).mean()
    q["DailyEMA50"]  = q["Date"].map(ema50.to_dict())
    q["DailyEMA200"] = q["Date"].map(ema200.to_dict())

    q["S1"] = (
        (q["Low"] < q["AsianLow"]) & (q["Close"] > q["AsianLow"]) &
        q["InSession"] & (q["Close"] > q["DailyEMA50"]) &
        ~q["HighVol"] & q["AsianLow"].notna()
    ).astype(int)

    q["S4"] = (
        (q["Low"] < q["AsianLow"]) & (q["Close"] > q["AsianLow"]) &
        q["InSession"] & (q["Close"] > q["DailyEMA50"]) &
        (q["DailyEMA50"] > q["DailyEMA200"]) &
        ~q["HighVol"] & q["AsianLow"].notna()
    ).astype(int)

    # Hourly ORB
    dclose = q[q.index.hour == 16][["Close"]].copy(); dclose.index = dclose.index.date
    dclose = dclose[~dclose.index.duplicated(keep="last")]
    sma200 = dclose["Close"].rolling(200).mean()
    bear200 = {d: (c < s) if not pd.isna(s) else False
               for d, c, s in zip(dclose.index, dclose["Close"], sma200)}
    q["Bear200"] = q["Date"].map(bear200).fillna(False).astype(bool)
    orb = q[q.index.hour == 9]
    ohi  = {d: r["High"]   for d, r in zip(orb["Date"], orb.to_dict("records"))}
    olo  = {d: r["Low"]    for d, r in zip(orb["Date"], orb.to_dict("records"))}
    ovol = {d: r["Volume"] for d, r in zip(orb["Date"], orb.to_dict("records"))}
    q["ORBHi"]  = q["Date"].map(ohi)
    q["ORBLo"]  = q["Date"].map(olo)
    q["ORBVol"] = q["Date"].map(ovol)
    q["ORBwin"] = q.index.map(lambda x: 10 <= x.hour <= 13)
    q["S5L"] = (q["ORBwin"] & (q["Close"] > q["ORBHi"]) &
                (q["DailyEMA50"] > q["DailyEMA200"]) &
                q["ORBHi"].notna() & (q["Volume"] > q["ORBVol"] * 0.6)).astype(int)
    q["S5S"] = (q["ORBwin"] & (q["Close"] < q["ORBLo"]) & q["Bear200"] &
                q["ORBLo"].notna() & (q["Volume"] > q["ORBVol"] * 0.6)).astype(int)
    return q


def load_vix():
    v = yf.download("^VIX", start="2018-01-01", end=str(date.today()), progress=False)["Close"]
    if isinstance(v, pd.DataFrame): v = v.iloc[:,0]
    return v


def run_qqq_intraday(df, sig, risk, sl, rr, vix, short=False):
    """Returns list of (date, dollar_pnl)."""
    rows = []; in_t = False; entry = stop = tgt = sh = 0.0; day_traded = None
    cap = 10_000; ds = cap; cur_date = None; lock = False

    def vmult(d):
        vix_ma = vix.rolling(21).mean().asof(pd.Timestamp(d))
        return 1.0 if pd.isna(vix_ma) else (0.0 if vix_ma > 25 else (0.5 if vix_ma >= 20 else 1.0))

    for i in range(1, len(df)):
        d     = df.index[i].date()
        price = float(df["Close"].iloc[i])
        s     = int(df[sig].iloc[i-1])
        vm    = vmult(d)
        if d != cur_date: cur_date = d; ds = cap; lock = False
        if (cap - ds) / max(ds, 1) <= -0.05 or (cap - 10_000) / 10_000 <= -0.10:
            lock = True
        if lock: continue
        if in_t:
            pnl = None
            if not short:
                if price <= stop: pnl = sh*(stop-entry) - sh*(entry+stop)*SLIP_QQQ
                elif price >= tgt: pnl = sh*(tgt-entry)  - sh*(entry+tgt)*SLIP_QQQ
            else:
                if price >= stop: pnl = sh*(entry-stop)  - sh*(entry+stop)*SLIP_QQQ
                elif price <= tgt: pnl = sh*(entry-tgt)  - sh*(entry+tgt)*SLIP_QQQ
            if pnl is not None:
                cap += pnl; rows.append((d, pnl)); in_t = False
        elif s == 1 and vm > 0 and day_traded != d:
            in_t = True; day_traded = d; entry = price
            if not short: stop = price*(1-sl); tgt = price*(1+sl*rr)
            else:         stop = price*(1+sl); tgt = price*(1-sl*rr)
            sh = (cap * risk * vm) / (price * sl)
    return rows


def load_gold_daily():
    g = yf.download("GLD", start="2018-06-01", end=str(date.today()),
                    progress=False, auto_adjust=True)
    if isinstance(g.columns, pd.MultiIndex): g.columns = g.columns.droplevel(1)
    g = g[["Open","High","Low","Close"]].dropna(); g.index = pd.to_datetime(g.index)
    g["e50"]  = g["Close"].ewm(span=50).mean()
    g["e200"] = g["Close"].ewm(span=200).mean()
    g["FVG"]  = ((g["Low"] > g["High"].shift(2)) & (g["Close"] > g["Open"]) &
                 (g["e50"] > g["e200"])).astype(int)
    return g


def run_gold(gw):
    SLIP_G = 0.0002; cap = 10_000; rows = []; it = False; e=s=t=sh=0.
    for i in range(1, len(gw)):
        p = float(gw["Close"].iloc[i]); sig = int(gw["FVG"].iloc[i-1])
        day = gw.index[i].date()
        if it:
            if p <= s: pnl=sh*(s-e)-sh*(e+s)*SLIP_G; cap+=pnl; rows.append((day,pnl)); it=False
            elif p >= t: pnl=sh*(t-e)-sh*(e+t)*SLIP_G; cap+=pnl; rows.append((day,pnl)); it=False
        elif sig:
            it=True; e=p; s=p*(1-0.012); t=p*(1+0.024); sh=(cap*0.005)/(p*0.012)
    return rows


def qqq_system_by_year(q, gold, vix, years):
    """Run all 5 sub-strategies, combine, return per-year returns and trades."""
    out = {}
    for Y in years:
        t1 = pd.Timestamp(f"{Y}-01-01", tz=eastern)
        t2 = pd.Timestamp(f"{Y}-12-31", tz=eastern)
        qy = q[(q.index >= t1) & (q.index <= t2)]
        gy = gold[(gold.index >= t1.tz_localize(None)) &
                  (gold.index <= t2.tz_localize(None))]

        ts1  = run_qqq_intraday(qy, "S1",  RISK_S1, STOP_S1, RR_S1, vix)
        ts4  = run_qqq_intraday(qy, "S4",  RISK_S4, STOP_S4, RR_S4, vix)
        ts5l = run_qqq_intraday(qy, "S5L", RISK_S5, STOP_S5, RR_S5, vix)
        ts5s = run_qqq_intraday(qy, "S5S", RISK_S5*0.6, STOP_S5, RR_S5, vix, short=True)
        tg   = run_gold(gy)
        all_t = ts1 + ts4 + ts5l + ts5s + tg
        n_trades = len(all_t)
        if not all_t:
            out[Y] = (0.0, 0.0, n_trades, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            continue
        cap   = 10_000.0
        by_day = {}
        for d, p in all_t:
            ts = pd.Timestamp(d); by_day[ts] = by_day.get(ts, 0.0) + p
        eq  = pd.Series(by_day).sort_index().cumsum() + cap
        eq  = eq.reindex(pd.date_range(eq.index.min(), eq.index.max(), freq="D"), method="ffill")
        ret = (eq.iloc[-1] / cap - 1)
        rets = eq.pct_change().fillna(0)
        vol  = rets.std() * np.sqrt(252)
        sh   = (rets.mean() * 252) / vol if vol > 0 else 0.0
        dd   = ((eq - eq.cummax()) / eq.cummax()).min()
        r_s1  = sum(p for _,p in ts1); r_s4  = sum(p for _,p in ts4)
        r_s5l = sum(p for _,p in ts5l); r_s5s = sum(p for _,p in ts5s); r_g = sum(p for _,p in tg)
        out[Y] = (ret, sh, n_trades, dd,
                  r_s1/cap, r_s4/cap, r_s5l/cap, r_s5s/cap, r_g/cap)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY B — BTC Funding Rate Fade
# ══════════════════════════════════════════════════════════════════════════════
THRESH_BTC = 0.0005   # 0.05%/8h
HOLD_H_BTC = 8
SL_BTC     = 0.020
RR_BTC     = 2.0
SLIP_BTC   = 0.0004
RISK_BTC   = 0.007


def load_btc_hourly():
    frames = []
    for Y in YEARS:
        p = os.path.join(DATA_DIR, f"btcusdt_perp_1m_{Y}.parquet")
        df = pd.read_parquet(p)
        frames.append(df.resample("1h").agg(
            Open=("Open","first"), High=("High","max"),
            Low=("Low","min"), Close=("Close","last"), Volume=("Volume","sum")
        ).dropna(subset=["Open"]))
    h = pd.concat(frames).sort_index()
    return h[~h.index.duplicated(keep="first")]


def load_funding():
    path = os.path.join(DATA_DIR, "btcusdt_funding.parquet")
    df   = pd.read_parquet(path)
    return df.iloc[:,0] if isinstance(df, pd.DataFrame) else df


def btc_by_year(h, funding, years):
    h = h.copy()
    h["funding"] = funding.reindex(h.index, method="ffill")
    h["sig_l"]   = (h["funding"] < -THRESH_BTC).astype(int)
    h["sig_s"]   = (h["funding"] >  THRESH_BTC).astype(int)
    out = {}
    for Y in years:
        sub = h[h.index.year == Y].copy()
        if len(sub) < 100:
            out[Y] = (0.0, 0.0, 0, 0.0); continue
        cap   = init = 10_000.0
        in_t  = False
        entry = stop = tgt = 0.0; long_t = True; held = 0
        n_t   = 0
        equity_curve = {sub.index[0]: cap}
        a_sl=sub["sig_l"].to_numpy(); a_ss=sub["sig_s"].to_numpy()
        a_c=sub["Close"].to_numpy(); a_h=sub["High"].to_numpy(); a_l=sub["Low"].to_numpy()
        pos = RISK_BTC / SL_BTC

        for i in range(1, len(sub)):
            if in_t:
                held += 1
                if long_t:
                    if a_l[i] <= stop:
                        cap += cap * pos * ((stop - entry)/entry - SLIP_BTC); in_t = False
                    elif a_h[i] >= tgt or held >= HOLD_H_BTC:
                        ex = tgt if a_h[i] >= tgt else a_c[i]
                        cap += cap * pos * ((ex - entry)/entry - SLIP_BTC); in_t = False
                else:
                    if a_h[i] >= stop:
                        cap += cap * pos * ((entry - stop)/entry - SLIP_BTC); in_t = False
                    elif a_l[i] <= tgt or held >= HOLD_H_BTC:
                        ex = tgt if a_l[i] <= tgt else a_c[i]
                        cap += cap * pos * ((entry - ex)/entry - SLIP_BTC); in_t = False
                if not in_t:
                    equity_curve[sub.index[i]] = cap
            else:
                if a_sl[i-1] == 1:
                    in_t = True; long_t = True; held = 0; n_t += 1
                    entry = a_c[i]; stop = entry*(1-SL_BTC); tgt = entry*(1+SL_BTC*RR_BTC)
                elif a_ss[i-1] == 1:
                    in_t = True; long_t = False; held = 0; n_t += 1
                    entry = a_c[i]; stop = entry*(1+SL_BTC); tgt = entry*(1-SL_BTC*RR_BTC)

        eq   = pd.Series(equity_curve).sort_index()
        eq   = eq.reindex(pd.date_range(eq.index.min(), eq.index.max(), freq="D"), method="ffill")
        ret  = (cap - init) / init
        rets = eq.pct_change().fillna(0)
        vol  = rets.std() * np.sqrt(252)
        sh   = (rets.mean() * 252) / vol if vol > 0 else 0.0
        dd   = ((eq - eq.cummax()) / eq.cummax()).min()
        out[Y] = (ret, sh, n_t, dd)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED (equal-weight allocation: 50/50 between QQQ system and BTC strategy)
# ══════════════════════════════════════════════════════════════════════════════
def combined_return(qqq_r, btc_r, w_qqq=0.5, w_btc=0.5):
    return w_qqq * qqq_r + w_btc * btc_r


# ══════════════════════════════════════════════════════════════════════════════
# KPIs over a multi-year dict of (ret, sharpe, n_trades, dd, ...)
# ══════════════════════════════════════════════════════════════════════════════
def summary(d, years, key_ret=0, key_sh=1, key_n=2, key_dd=3):
    rets  = [d[Y][key_ret] for Y in years]
    shps  = [d[Y][key_sh]  for Y in years if d[Y][key_sh] != 0]
    dds   = [d[Y][key_dd]  for Y in years]
    ns    = [d[Y][key_n]   for Y in years]
    IN    = np.mean([d[Y][key_ret] for Y in (2021, 2022)])
    OUT   = np.mean([d[Y][key_ret] for Y in (2023, 2024)])
    avg   = np.mean(rets)
    return dict(per_year=rets, avg=avg, IN=IN, oos=OUT,
                sharpe=np.mean(shps) if shps else 0.0,
                max_dd=min(dds), trades_yr=np.mean(ns))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
print("Loading QQQ hourly data...")
q = load_qqq()
print("Building QQQ signals...")
q = build_qqq_signals(q)
print("Loading VIX and Gold...")
vix  = load_vix()
gold = load_gold_daily()

print("Loading BTC perp hourly + funding...")
btc_h   = load_btc_hourly()
funding = load_funding()

print("\nRunning backtests (2021-2024)...\n")
qqq_r = qqq_system_by_year(q, gold, vix, YEARS)
btc_r = btc_by_year(btc_h, funding, YEARS)

qqq_s = summary(qqq_r, YEARS, key_ret=0, key_sh=1, key_n=2, key_dd=3)
btc_s = summary(btc_r, YEARS, key_ret=0, key_sh=1, key_n=2, key_dd=3)

W = 78
print("=" * W)
print(f"STRATEGY COMPARISON — 2021–2024  |  IN=2021-22  |  OOS=2023-24")
print("=" * W)

# ── Per-year table ────────────────────────────────────────────────────────────
hdr = f"  {'':25}" + "".join(f"{Y:>8}" for Y in YEARS) + f"{'avg':>7}{'IN':>7}{'OOS':>8}"
print(hdr); print("  " + "-"*(25 + 8*4 + 22))

for label, s in [("QQQ System (S1+S4+S5+Gold)", qqq_s), ("BTC Funding Fade", btc_s)]:
    row = f"  {label:<25}" + "".join(f"{s['per_year'][i]:>+8.1%}" for i in range(4))
    row += f"{s['avg']:>+7.1%}{s['IN']:>+7.1%}{s['oos']:>+8.1%}"
    print(row)

# Combined
cmb_per = [combined_return(qqq_r[Y][0], btc_r[Y][0]) for Y in YEARS]
cmb_IN  = np.mean(cmb_per[:2]); cmb_OUT = np.mean(cmb_per[2:])
row = f"  {'Combined (50/50)':<25}" + "".join(f"{r:>+8.1%}" for r in cmb_per)
row += f"{np.mean(cmb_per):>+7.1%}{cmb_IN:>+7.1%}{cmb_OUT:>+8.1%}"
print(row)

# ── KPI table ─────────────────────────────────────────────────────────────────
print()
print(f"  {'KPI':28} {'QQQ System':>12} {'BTC Fade':>12} {'Combined':>12}")
print("  " + "-"*66)
kpi_rows = [
    ("Avg annual return",    f"{qqq_s['avg']:>+12.1%}",          f"{btc_s['avg']:>+12.1%}",       f"{np.mean(cmb_per):>+12.1%}"),
    ("OOS return (2023-24)", f"{qqq_s['oos']:>+12.1%}",          f"{btc_s['oos']:>+12.1%}",       f"{cmb_OUT:>+12.1%}"),
    ("Avg Sharpe",           f"{qqq_s['sharpe']:>12.2f}",        f"{btc_s['sharpe']:>12.2f}",     f"{'n/a':>12}"),
    ("Worst drawdown",       f"{qqq_s['max_dd']:>12.1%}",        f"{btc_s['max_dd']:>12.1%}",     f"{'n/a':>12}"),
    ("Trades per year",      f"{qqq_s['trades_yr']:>12.0f}",     f"{btc_s['trades_yr']:>12.0f}",  f"{'—':>12}"),
]
for label, qa, ba, ca in kpi_rows:
    print(f"  {label:<28} {qa} {ba} {ca}")

# ── QQQ sub-strategy breakdown ────────────────────────────────────────────────
print()
print(f"  QQQ SYSTEM — per sub-strategy contribution (avg annual %)")
print(f"  {'Sub-strat':12}" + "".join(f"{Y:>8}" for Y in YEARS) + f"{'avg':>7}")
print("  " + "-"*55)
for name, idx in [("S1 (Asian L)", 4), ("S4 (Asian+EMA)", 5),
                  ("S5L (ORB long)", 6), ("S5S (ORB short)", 7), ("Gold FVG", 8)]:
    vals = [qqq_r[Y][idx] for Y in YEARS]
    row  = f"  {name:<12}" + "".join(f"{v:>+8.1%}" for v in vals) + f"{np.mean(vals):>+7.1%}"
    print(row)

# ── Correlation note ──────────────────────────────────────────────────────────
print()
qqq_ann = np.array([qqq_r[Y][0] for Y in YEARS])
btc_ann = np.array([btc_r[Y][0]  for Y in YEARS])
corr    = np.corrcoef(qqq_ann, btc_ann)[0,1] if len(YEARS) > 2 else float("nan")
print(f"  Annual return correlation (QQQ vs BTC): {corr:>+.2f}")
print(f"  (close to 0 = strategies are independent; close to 1 = both win/lose together)")

# ── OOS verdict ────────────────────────────────────────────────────────────────
print()
print("=" * W)
print("VERDICT")
print("=" * W)
print()
print(f"  QQQ System:")
if qqq_s["oos"] > 0.03:
    print(f"    OOS {qqq_s['oos']:+.1%} → solid edge, deployable on paper/live")
elif qqq_s["oos"] > 0:
    print(f"    OOS {qqq_s['oos']:+.1%} → weakly positive, trade small size")
else:
    print(f"    OOS {qqq_s['oos']:+.1%} → negative OOS, do not deploy as-is")

print()
print(f"  BTC Funding Fade:")
if btc_s["oos"] > 0.03:
    print(f"    OOS {btc_s['oos']:+.1%} → solid edge, deployable on Bybit/Binance perp")
elif btc_s["oos"] > 0:
    print(f"    OOS {btc_s['oos']:+.1%} → weakly positive, trade very small size only")
else:
    print(f"    OOS {btc_s['oos']:+.1%} → negative OOS, do not deploy")

print()
print(f"  Combined (50/50):")
if cmb_OUT > 0.02:
    print(f"    OOS {cmb_OUT:+.1%} → diversification benefit: "
          f"{'correlation benefit' if corr < 0.3 else 'limited correlation benefit'}")
else:
    print(f"    OOS {cmb_OUT:+.1%} → combined edge similar to individual strategies")

print()
print(f"  Practical deployment:")
print(f"    QQQ system → Alpaca paper first (US hours only, ~{qqq_s['trades_yr']:.0f} trades/yr)")
print(f"    BTC fade   → Bybit/Binance perp, 0.7% risk/trade, LIMIT orders")
print(f"               → set up at 00:00 / 08:00 / 16:00 UTC (every 8h)")
print(f"               → use btc_funding_reversal.py signal logic")
print("=" * W)
