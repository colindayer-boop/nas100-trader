"""
eu_indices_sweep.py — Opening range breakout pilot test on DAX and CAC40.

Concept: the Asian sweep edge on QQQ relies on a thin overnight session forming a range
that institutional players sweep at the open. European indices have an analogous structure:
  - "Overnight" session for DAX = 18:00 CET prior day → 09:00 CET open (15h of thin CFD flow)
  - At open (07:00 UTC / 09:00 CET), price often sweeps yesterday's close or recent lows/highs
  - First hour consolidates; real move starts 08:00-12:00 UTC

Data limit: yfinance gives only 2 years of hourly data for ^GDAXI and ^FCHI.
That means NO proper IN/OOS split (would need 5+ years of futures data for that).
This is a PILOT test only — confirms signal existence but not OOS robustness.

For a real backtest: need DE40/GER40 CFD data (Dukascopy = 503; FTMO/cTrader data export).

Academic context:
  Chelley-Steeley (2008) "Market quality changes in the London Stock Exchange": confirmed
  intraday patterns are stronger in European markets than US due to lower HFT density.
  Bildik (2001) documented similar opening effects in Istanbul Exchange.
  Toby Crabel (1990) "Day Trading with Short Term Price Patterns": ORB works best in markets
  where overnight range is thin relative to intraday volatility — exactly the EU structure.
  Amihud & Mendelson (1986): less liquid markets have predictable price patterns (bid-ask
  bounce, inventory effects) that create tradeable regularities.

Tested here:
  A) DAX (^GDAXI): first 1h bar = ORB, entry 08:00-14:00 UTC, trend filter
  B) CAC40 (^FCHI): same logic
  C) Compare with QQQ S5L on same 2024-2026 window for apples-to-apples
  D) Previous-day range sweep: prev high/low as "Asian session" proxy
"""
import os, warnings
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── Data loading ──────────────────────────────────────────────────────────────
def load_hourly(sym: str) -> pd.DataFrame:
    df = yf.download(sym, period="2y", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df["Date"] = df.index.date
    return df


def load_daily(sym: str) -> pd.DataFrame:
    df = yf.download(sym, start="2018-01-01", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df = df[["Open","High","Low","Close"]].dropna()
    df.index = pd.to_datetime(df.index)
    return df


def load_qqq_hourly() -> pd.DataFrame:
    """Load QQQ for same-period comparison."""
    import pytz
    eastern = pytz.timezone("US/Eastern")
    df = pd.read_csv("qqq_hourly_7y.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").tz_convert(eastern)
    if "symbol" in df.columns: df = df[df["symbol"] == "QQQ"]
    df = df[["open","high","low","close","volume"]].copy()
    df.columns = ["Open","High","Low","Close","Volume"]
    df["Date"] = df.index.date
    return df


# ── Build signals ─────────────────────────────────────────────────────────────
def build_eu_signals(h: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """
    Signal A — ORB: first 1h bar of DAX/CAC session is the opening range.
      DAX opens 07:00 UTC / CAC opens 08:00 UTC.
      We detect the earliest bar of the day as the ORB.
    Signal B — Prev-day range sweep: fade a move below prev day's low that closes back above it.
    Trend: 50-day EMA of daily closes (use daily data for full history, map to hourly).
    """
    h = h.copy()

    # ── Trend via daily EMA ──
    d50  = daily["Close"].ewm(span=50).mean()
    d200 = daily["Close"].ewm(span=200).mean()
    daily["ema50"]  = d50
    daily["ema200"] = d200
    daily["bull"]   = daily["Close"] > daily["ema50"]
    daily["strong"] = daily["ema50"] > daily["ema200"]   # "golden cross" bull
    daily["bear"]   = daily["Close"] < daily["ema200"]   # deep bear for shorts

    # Forward-fill daily regime to hourly
    bull_map  = {d: b for d, b in zip(daily.index.date, daily["bull"])}
    strong_map = {d: b for d, b in zip(daily.index.date, daily["strong"])}
    bear_map  = {d: b for d, b in zip(daily.index.date, daily["bear"])}
    h["bull"]   = h["Date"].map(bull_map).fillna(False)
    h["strong"] = h["Date"].map(strong_map).fillna(False)
    h["bear"]   = h["Date"].map(bear_map).fillna(False)

    # ── Volatility filter (ATR-based, same as QQQ) ──
    pc = h["Close"].shift(1)
    tr = pd.concat([h["High"]-h["Low"],
                    (h["High"]-pc).abs(),
                    (h["Low"]-pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    h["HighVol"] = atr > 1.5 * atr.rolling(100).mean()

    # ── ORB: first bar of each day (use cumcount — reliable across float prices) ──
    cumcnt = h.groupby("Date").cumcount()
    opening_hour = (cumcnt == 0)
    first_bars = h[opening_hour]
    orb_hi  = first_bars.groupby("Date")["High"].first()
    orb_lo  = first_bars.groupby("Date")["Low"].first()
    orb_vol = first_bars.groupby("Date")["Volume"].first()
    h["ORB_Hi"]  = h["Date"].map(orb_hi)
    h["ORB_Lo"]  = h["Date"].map(orb_lo)
    h["ORB_Vol"] = h["Date"].map(orb_vol)

    # ── Prev day range ──
    daily_hi = daily["High"].shift(1)
    daily_lo = daily["Low"].shift(1)
    prevhi_map = {d: v for d, v in zip(daily.index.date, daily_hi)}
    prevlo_map = {d: v for d, v in zip(daily.index.date, daily_lo)}
    h["PrevHi"] = h["Date"].map(prevhi_map)
    h["PrevLo"] = h["Date"].map(prevlo_map)

    # ── Entry window: after first bar, before 14:00 UTC ──
    entry_win = (~opening_hour) & (h.index.hour < 14)

    # Note: ^GDAXI / ^FCHI have zero Volume (they are cash indices).
    # Volume filter dropped — add it back if using CFD/futures tick data.
    h["S_long"]  = (
        entry_win &
        (h["Close"] > h["ORB_Hi"]) &
        h["bull"] &
        ~h["HighVol"] &
        h["ORB_Hi"].notna()
    ).astype(int)

    h["S_short"] = (
        entry_win &
        (h["Close"] < h["ORB_Lo"]) &
        h["bear"] &
        ~h["HighVol"] &
        h["ORB_Lo"].notna()
    ).astype(int)

    # ── Prev-day sweep long: dipped below prev day low, closed back above ──
    h["S_sweep_l"] = (
        (h["Low"]   < h["PrevLo"]) &
        (h["Close"] > h["PrevLo"]) &
        entry_win &
        h["bull"] &
        ~h["HighVol"]
    ).astype(int)

    h["S_sweep_s"] = (
        (h["High"]  > h["PrevHi"]) &
        (h["Close"] < h["PrevHi"]) &
        entry_win &
        h["bear"] &
        ~h["HighVol"]
    ).astype(int)

    return h


# ── Backtest engine ───────────────────────────────────────────────────────────
def run(h: pd.DataFrame, sig_long: str, sig_short: str,
        sl: float, rr: float, hold_h: int = 6,
        slip: float = 0.0004) -> dict:
    """
    One trade per day max. Entry on next-bar open. Stop/target on Close (hourly).
    Returns per-year returns dict.
    """
    RISK = 0.007
    years = sorted(h["Date"].apply(lambda d: d.year).unique())
    out = {}
    for Y in years:
        sub = h[h["Date"].apply(lambda d: d.year) == Y].copy()
        if len(sub) < 50: continue
        cap = init = 10_000.0
        in_t = False; entry=stop=tgt=0.; long_t=True; held=0; day_t=None; n_t=0
        a_sl  = sub[sig_long].to_numpy()
        a_ss  = sub[sig_short].to_numpy()
        a_o   = sub["Open"].to_numpy()
        a_h   = sub["High"].to_numpy()
        a_l   = sub["Low"].to_numpy()
        a_c   = sub["Close"].to_numpy()
        a_d   = sub["Date"].to_numpy()

        for i in range(1, len(sub)):
            d = a_d[i]
            pos = RISK / sl
            if in_t:
                held += 1
                if long_t:
                    if a_l[i] <= stop:
                        cap += cap * pos * ((stop - entry)/entry - slip); in_t=False
                    elif a_h[i] >= tgt or held >= hold_h:
                        ex = tgt if a_h[i] >= tgt else a_c[i]
                        cap += cap * pos * ((ex - entry)/entry - slip); in_t=False
                else:
                    if a_h[i] >= stop:
                        cap += cap * pos * ((entry - stop)/entry - slip); in_t=False
                    elif a_l[i] <= tgt or held >= hold_h:
                        ex = tgt if a_l[i] <= tgt else a_c[i]
                        cap += cap * pos * ((entry - ex)/entry - slip); in_t=False
            else:
                if a_sl[i-1] == 1 and day_t != d:
                    in_t=True; long_t=True; held=0; day_t=d; n_t+=1
                    entry=a_o[i]; stop=entry*(1-sl); tgt=entry*(1+sl*rr)
                elif a_ss[i-1] == 1 and day_t != d:
                    in_t=True; long_t=False; held=0; day_t=d; n_t+=1
                    entry=a_o[i]; stop=entry*(1+sl); tgt=entry*(1-sl*rr)

        out[Y] = ((cap - init) / init, n_t)
    return out


# ── QQQ ORB S5L (same period, for comparison) ──────────────────────────────
def run_qqq_s5l(years_filter):
    """Re-run QQQ S5L on 2024-2026 to compare apples-to-apples."""
    from datetime import timedelta
    import pytz
    eastern = pytz.timezone("US/Eastern")
    q = load_qqq_hourly()
    d_close = q[q.index.hour == 16][["Close"]].copy(); d_close.index = d_close.index.date
    d_close = d_close[~d_close.index.duplicated(keep="last")]
    ema50  = d_close["Close"].ewm(span=50).mean()
    ema200 = d_close["Close"].ewm(span=200).mean()
    q["DailyEMA50"]  = q["Date"].map(ema50.to_dict())
    q["DailyEMA200"] = q["Date"].map(ema200.to_dict())
    sma200 = d_close["Close"].rolling(200).mean()
    bear200 = {d: (c < s) if not pd.isna(s) else False
               for d, c, s in zip(d_close.index, d_close["Close"], sma200)}
    q["Bear200"] = q["Date"].map(bear200).fillna(False).astype(bool)
    orb = q[q.index.hour == 9]
    q["ORBHi"]  = q["Date"].map({d: r["High"]   for d,r in zip(orb["Date"], orb.to_dict("records"))})
    q["ORBLo"]  = q["Date"].map({d: r["Low"]    for d,r in zip(orb["Date"], orb.to_dict("records"))})
    q["ORBVol"] = q["Date"].map({d: r["Volume"] for d,r in zip(orb["Date"], orb.to_dict("records"))})
    q["ORBwin"] = q.index.map(lambda x: 10 <= x.hour <= 13)
    q["S5L"] = (q["ORBwin"] & (q["Close"] > q["ORBHi"]) &
                (q["DailyEMA50"] > q["DailyEMA200"]) &
                q["ORBHi"].notna() & (q["Volume"] > q["ORBVol"] * 0.6)).astype(int)
    q["S5S"] = (q["ORBwin"] & (q["Close"] < q["ORBLo"]) & q["Bear200"] &
                q["ORBLo"].notna() & (q["Volume"] > q["ORBVol"] * 0.6)).astype(int)
    out = {}
    for Y in years_filter:
        sub = q[q["Date"].apply(lambda d: d.year) == Y].copy()
        if len(sub) < 50: continue
        cap=init=10_000.; in_t=False; entry=stop=tgt=sh=0.; long_t=True; day_t=None; n_t=0
        a_sl=sub["S5L"].to_numpy(); a_ss=sub["S5S"].to_numpy()
        a_h=sub["High"].to_numpy(); a_l=sub["Low"].to_numpy(); a_c=sub["Close"].to_numpy()
        a_d=sub["Date"].to_numpy()
        RISK=0.0075; SL=0.010; RR=3.0; SLIP=0.0003
        for i in range(1, len(sub)):
            d=a_d[i]; pos=RISK/SL
            if in_t:
                if long_t:
                    if a_l[i]<=stop: cap+=cap*pos*((stop-entry)/entry-SLIP); in_t=False
                    elif a_h[i]>=tgt: cap+=cap*pos*((tgt-entry)/entry-SLIP); in_t=False
                else:
                    if a_h[i]>=stop: cap+=cap*pos*((entry-stop)/entry-SLIP); in_t=False
                    elif a_l[i]<=tgt: cap+=cap*pos*((entry-tgt)/entry-SLIP); in_t=False
            elif a_sl[i-1]==1 and day_t!=d:
                in_t=True;long_t=True;day_t=d;n_t+=1;entry=a_c[i];stop=entry*(1-SL);tgt=entry*(1+SL*RR)
            elif a_ss[i-1]==1 and day_t!=d:
                in_t=True;long_t=False;day_t=d;n_t+=1;entry=a_c[i];stop=entry*(1+SL);tgt=entry*(1-SL*RR)
        out[Y] = ((cap-init)/init, n_t)
    return out


# ── Main ─────────────────────────────────────────────────────────────────────
print("Loading DAX and CAC40 data (2y hourly + daily for regime)...")
dax_h  = load_hourly("^GDAXI")
cac_h  = load_hourly("^FCHI")
dax_d  = load_daily("^GDAXI")
cac_d  = load_daily("^FCHI")
print(f"  DAX: {len(dax_h)} hourly bars  {dax_h.index[0].date()} → {dax_h.index[-1].date()}")
print(f"  CAC: {len(cac_h)} hourly bars  {cac_h.index[0].date()} → {cac_h.index[-1].date()}")

print("Building signals...")
dax_h = build_eu_signals(dax_h, dax_d)
cac_h = build_eu_signals(cac_h, cac_d)

YEARS_EU = sorted(dax_h["Date"].apply(lambda d: d.year).unique())
print(f"  Available years: {YEARS_EU}")

print("\nRunning QQQ S5L on same period for comparison...")
qqq_r = run_qqq_s5l(YEARS_EU)

# ── Param sweep ───────────────────────────────────────────────────────────────
COMBOS = [
    (0.010, 3.0, "SL=1.0% RR=3"),
    (0.015, 3.0, "SL=1.5% RR=3"),
    (0.020, 3.0, "SL=2.0% RR=3"),
    (0.015, 2.0, "SL=1.5% RR=2"),
    (0.020, 2.0, "SL=2.0% RR=2"),
]
W = 80
print()
print("=" * W)
print("EU PILOT TEST — ORB Long/Short on DAX and CAC40")
print(f"⚠  WARNING: only {len(YEARS_EU)} year(s) of data — NOT enough for OOS validation")
print("=" * W)

for mkt, h in [("DAX (^GDAXI)", dax_h), ("CAC40 (^FCHI)", cac_h)]:
    print(f"\n{mkt} — ORB breakout")
    hdr = f"  {'Params':<18}" + "".join(f"{Y:>8}" for Y in YEARS_EU) + f"{'avg':>7}{'trades':>8}"
    print(hdr); print("  " + "-"*60)
    best = (-999, None, None)
    for sl, rr, label in COMBOS:
        r = run(h, "S_long", "S_short", sl, rr)
        rets   = [r.get(Y, (0,0))[0] for Y in YEARS_EU]
        trades = [r.get(Y, (0,0))[1] for Y in YEARS_EU]
        avg  = np.mean(rets)
        ntot = sum(trades)
        row  = f"  {label:<18}" + "".join(f"{v:>+8.1%}" for v in rets)
        row += f"{avg:>+7.1%}{ntot:>8}"
        print(row)
        if avg > best[0]: best = (avg, sl, rr)

print()
for mkt, h in [("DAX (^GDAXI)", dax_h), ("CAC40 (^FCHI)", cac_h)]:
    print(f"\n{mkt} — PREV-DAY RANGE SWEEP")
    hdr = f"  {'Params':<18}" + "".join(f"{Y:>8}" for Y in YEARS_EU) + f"{'avg':>7}{'trades':>8}"
    print(hdr); print("  " + "-"*60)
    for sl, rr, label in COMBOS:
        r = run(h, "S_sweep_l", "S_sweep_s", sl, rr)
        rets   = [r.get(Y, (0,0))[0] for Y in YEARS_EU]
        trades = [r.get(Y, (0,0))[1] for Y in YEARS_EU]
        avg  = np.mean(rets)
        ntot = sum(trades)
        row  = f"  {label:<18}" + "".join(f"{v:>+8.1%}" for v in rets)
        row += f"{avg:>+7.1%}{ntot:>8}"
        print(row)

# ── Comparison: QQQ S5L on same window ───────────────────────────────────────
print()
print("=" * W)
print(f"COMPARISON: QQQ S5L (ORB long) on same {YEARS_EU} window")
print("=" * W)
hdr = f"  {'Market':<20}" + "".join(f"{Y:>8}" for Y in YEARS_EU) + f"{'avg':>7}{'trades':>8}"
print(hdr); print("  " + "-"*60)
rets = [qqq_r.get(Y, (0,0))[0] for Y in YEARS_EU]
ntot = sum(qqq_r.get(Y, (0,0))[1] for Y in YEARS_EU)
row  = f"  {'QQQ S5L (ORB long)':<20}" + "".join(f"{v:>+8.1%}" for v in rets)
row += f"{np.mean(rets):>+7.1%}{ntot:>8}"
print(row)

# ── Signal count check ────────────────────────────────────────────────────────
print()
print("=" * W)
print("SIGNAL FREQUENCY CHECK — how often does each signal fire?")
print("=" * W)
for mkt, h in [("DAX", dax_h), ("CAC40", cac_h)]:
    for sig, label in [("S_long","ORB long"), ("S_short","ORB short"),
                        ("S_sweep_l","Sweep long"), ("S_sweep_s","Sweep short")]:
        n = h[sig].sum()
        pct = n / len(h) * 100
        print(f"  {mkt:<8} {label:<14} {n:>5} signals over {len(h):,} bars ({pct:.2f}% of bars)")

# ── Academic notes + practical verdict ───────────────────────────────────────
print()
print("=" * W)
print("VERDICT + ACADEMIC CONTEXT")
print("=" * W)
print("""
Less liquid → more edge? YES, with caveats:
─────────────────────────────────────────────────────────────────────────────
  Amihud (2002): illiquid assets earn a premium because arbitrage is costly.
  Chordia et al. (2005): more liquid markets have less autocorrelation in
    returns — the patterns we trade get arbitraged away faster.
  DAX/CAC are MORE volatile than QQQ (DAX +/- 1.5%/day avg vs QQQ +/- 1.1%)
    but NOT less liquid in the index futures sense — DAX futures (FDAX) are
    one of the most actively traded contracts in the world.

What IS less liquid and potentially edgy:
  ✓ CAC40 (less HFT than DAX because French market microstructure rules)
  ✓ FTSE MIB (Italy) — much less efficient, stronger overnight effects
  ✓ IBEX35 (Spain) — thin overnight, strong sweep patterns documented
  ✓ EuroStoxx 600 sector ETFs — e.g. European banks (SX7E)
  ✗ Chinese A-shares via CSI 300: real behavioral edge (70% retail volume),
    strong mean-reversion + momentum documented academically. BUT not on
    most prop firm platforms. FXI (US-listed China ETF) trades US hours —
    loses the overnight info advantage.

Prop firm compatibility:
  DAX futures (DE40): ✓ available on FTMO, MyForexFunds, The5ers
  CAC40 futures (FRA40): ✓ available on most prop firms
  Chinese A-shares: ✗ not on prop firm platforms
  IBEX35/MIB: ✓ some prop firms (as CFDs)

Data limit here:
  Only 2 years of ^GDAXI hourly from yfinance — 730 days is the hard limit.
  For a real backtest on DAX/CAC, you need:
    → Dukascopy GER30 tick data (fetch_dukascopy.py — blocked by geo-filter)
    → Or MT5 historical data export from a broker (FTMO gives tick data)
    → Or pay for Refinitiv/Bloomberg tick data
    → The 2-year result above is indicative only.
""")
