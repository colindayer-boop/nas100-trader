"""
master_backtest.py — 5 strategies, shared $10,000 capital
Improvements:
  1. Vol scaling  — Barroso & Santa-Clara (2015): size ∝ target_vol / realized_vol
  2. TSMOM filter — Moskowitz, Ooi & Pedersen (2012): QQQ 12-month return gate
  3. S5 ORB       — 5-min opening range, entry 9:35am-1pm, 1-min data
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import pytz
import yfinance as yf

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
INITIAL      = 10_000
DAILY_LIMIT  = 0.05
DD_LIMIT     = 0.10
MONTHLY_TGT  = 0.08   # 8% → pause rest of month

# Risk per trade (doubled from original session for prop firm 8% target)
RISK_S1 = 0.0070;  STOP_S1 = 0.015;  RR_S1 = 3.0
RISK_S2 = 0.0050;  STOP_S2 = 0.015;  RR_S2 = 3.0
RISK_S3 = 0.0040;  STOP_S3 = 0.020;  HOLD_S3 = 5
RISK_S4 = 0.0040;  STOP_S4 = 0.015;  RR_S4 = 3.0
RISK_S5 = 0.0075;  STOP_S5 = 0.010;  RR_S5 = 3.0   # ORB: 0.75%/trade
MAX_DAY_RISK = 0.0300
TARGET_VOL   = 0.12   # Barroso & Santa-Clara: 12% ann. vol target

S3_SYMS = ["QQQ", "GLD", "GDX", "SLV", "USO"]
S4_SYMS = ["QQQ", "SPY"]
eastern  = pytz.timezone("US/Eastern")

# ── LOAD HOURLY DATA ──────────────────────────────────────────────────────────
print("Loading hourly data...")

def load_hourly(path, sym):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    df = df[df["symbol"] == sym]
    df.index = df.index.tz_convert(eastern)
    d = df[["open","high","low","close","volume"]].copy()
    d.columns = ["Open","High","Low","Close","Volume"]
    return d

qqq_h = load_hourly("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv", "QQQ")
spy_h = load_hourly("/Users/colindayer/nas100_backtest/spy_hourly_7y.csv", "SPY")
gld_h = load_hourly("/Users/colindayer/nas100_backtest/gld_hourly_7y.csv", "GLD")

start_str = str(qqq_h.index.min().date())
end_str   = str(qqq_h.index.max().date() + pd.Timedelta(days=5))

# ── DOWNLOAD DAILY DATA ───────────────────────────────────────────────────────
print("Downloading daily data...")
daily = {}
for sym in ["^VIX", "SPY"] + S3_SYMS:
    d = yf.download(sym, start=start_str, end=end_str,
                    interval="1d", progress=False, auto_adjust=True)
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    daily[sym] = d

# --- S6: SMA 5/20 crossover signal (daily) ---
# --- S6: SMA 5/20 crossover signal (daily) ---
close_q = daily["QQQ"]["Close"].squeeze()
ma_fast = close_q.rolling(5).mean()
ma_slow = close_q.rolling(20).mean()
sig_raw = (ma_fast > ma_slow).astype(int)*2 - 1  # 1 for long, -1 for short
s6_sig = {d.date(): v for d, v in sig_raw.shift(1).fillna(0).items()}  # lagged signal
s6_open = {d.date(): v for d, v in daily["QQQ"]["Open"].squeeze().items()}
s6_close = {d.date(): v for d, v in daily["QQQ"]["Close"].squeeze().items()}

# ── REGIME & FILTER MAPS ──────────────────────────────────────────────────────
vix_ma21   = daily["^VIX"]["Close"].squeeze().rolling(21).mean()
spy_ema50  = daily["SPY"]["Close"].squeeze().ewm(span=50,  adjust=False).mean()
spy_ema200 = daily["SPY"]["Close"].squeeze().ewm(span=200, adjust=False).mean()
spy_golden = spy_ema50 > spy_ema200

def get_regime(d, include_spy_dc):
    """'halt' | 'defensive' | 'normal'"""
    dt  = pd.Timestamp(d)
    vix = vix_ma21.asof(dt)
    if pd.isna(vix): vix = 0.0
    vix = float(vix)
    if vix > 35: return "halt"
    if vix > 25: return "defensive"
    if include_spy_dc:
        spy = spy_golden.asof(dt)
        if not pd.isna(spy) and not bool(spy):
            return "defensive"
    return "normal"

# Vol scaling (Barroso & Santa-Clara 2015): realized vol from QQQ daily returns
_qqq_ret  = daily["QQQ"]["Close"].squeeze().pct_change()
_qqq_rvol = _qqq_ret.rolling(21).std() * np.sqrt(252)
_vol_mult  = (TARGET_VOL / _qqq_rvol).clip(0.25, 2.0)

def vol_mult_for(d):
    v = _vol_mult.asof(pd.Timestamp(d))
    return float(v) if not pd.isna(v) else 1.0

# TSMOM (Moskowitz, Ooi & Pedersen 2012): QQQ 12-month return signal
_qqq_12mo = daily["QQQ"]["Close"].squeeze().pct_change(252)

def tsmom_for(d):
    v = _qqq_12mo.asof(pd.Timestamp(d))
    return float(v) if not pd.isna(v) else 0.01   # default positive

# S3 daily signals
def s3_signals(sym):
    d = daily[sym]
    c, o, v = d["Close"].squeeze(), d["Open"].squeeze(), d["Volume"].squeeze()
    vm = v.rolling(66).mean().shift(1)
    vs = v.rolling(66).std().shift(1)
    return ((v - vm) / vs > 1.5) & ((c - o) / o > 0.01)

s3_sig = {sym: s3_signals(sym) for sym in S3_SYMS}

# ── HOURLY SIGNAL COMPUTATION ─────────────────────────────────────────────────
print("Computing hourly signals...")

def asian_hl(data):
    d = data.copy()
    d["Date"] = d.index.date
    d["Asian"] = d.index.map(lambda x: x.hour >= 18 or x.hour < 2)
    d["SD"]    = d.index.map(
        lambda x: (x + pd.Timedelta(days=1)).date() if x.hour >= 18 else x.date())
    ab = d[d["Asian"]]
    d["AH"] = d["SD"].map(ab.groupby("SD")["High"].max())
    d["AL"] = d["SD"].map(ab.groupby("SD")["Low"].min())
    return d

def daily_ema(data, span, hour=16):
    dc = data[data.index.hour == hour][["Close"]].copy()
    dc.index = dc.index.date
    dc = dc[~dc.index.duplicated(keep="last")]
    return data["Date"].map(dc["Close"].ewm(span=span).mean().to_dict())

def compute_s1(raw):
    d = asian_hl(raw); d["Date"] = d.index.date
    close, high, low = d["Close"], d["High"], d["Low"]
    d["RTH"] = d.index.map(lambda x: 9 <= x.hour < 16)
    d["TP"]  = (high + low + close) / 3
    vv = []; ct = cv = 0.0; pd_ = None
    for i in range(len(d)):
        r = d.iloc[i]
        if r["Date"] != pd_: ct = cv = 0.0; pd_ = r["Date"]
        if r["RTH"] and r["Volume"] > 0: ct += r["TP"]*r["Volume"]; cv += r["Volume"]
        vv.append(ct/cv if cv > 0 else float("nan"))
    d["VWAP"]      = vv
    d["BullVWAP"]  = close > d["VWAP"]
    d["InSession"] = d.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
    pc = close.shift(1)
    tr = pd.concat([high-low,(high-pc).abs(),(low-pc).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    d["HighVol"]  = atr > 1.5 * atr.rolling(200).mean()
    d["DEMA50"]   = daily_ema(d, 50)
    d["Uptrend"]  = close > d["DEMA50"]
    d["Sig"] = ((low < d["AL"]) & (close > d["AL"]) & d["AL"].notna() &
                d["InSession"] & d["BullVWAP"] & d["Uptrend"] & ~d["HighVol"]).astype(int)
    return d

def compute_s2(raw):
    d = asian_hl(raw); d["Date"] = d.index.date
    close, high, low, open_ = d["Close"], d["High"], d["Low"], d["Open"]
    d["InLondon"]    = d.index.map(lambda x: 2 <= x.hour < 5)
    cbr              = (high - low).replace(0, 0.001)
    d["StrongCandle"] = (close - open_).abs() / cbr > 0.6
    d["FVG_Up"]      = low > high.shift(2)
    d["FVG_Down"]    = high < low.shift(2)
    d["SweepHigh"]   = (high > d["AH"]) & (close < d["AH"])
    d["SweepLow"]    = (low  < d["AL"]) & (close > d["AL"])
    sha = pd.Series(False, index=d.index); sla = pd.Series(False, index=d.index)
    hb = lb = -999
    for i in range(len(d)):
        if d["SweepHigh"].iloc[i]: hb = i
        if d["SweepLow"].iloc[i]:  lb = i
        sha.iloc[i] = (i - hb) <= 10; sla.iloc[i] = (i - lb) <= 10
    d["SHA"] = sha; d["SLA"] = sla
    d["DEMA50"]    = daily_ema(d, 50)
    d["Uptrend"]   = close > d["DEMA50"]
    d["Downtrend"] = close < d["DEMA50"]
    d["Sig"] = 0
    d.loc[d["SLA"] & d["InLondon"] & d["StrongCandle"] &
          d["FVG_Up"] & d["Uptrend"] & d["AL"].notna(), "Sig"] = 1
    d.loc[d["SHA"] & d["InLondon"] & d["StrongCandle"] &
          d["FVG_Down"] & d["Downtrend"] & d["AH"].notna(), "Sig"] = -1
    return d

def compute_s4(raw):
    d = asian_hl(raw); d["Date"] = d.index.date
    close, high, low = d["Close"], d["High"], d["Low"]
    day_low  = d.groupby("Date")["Low"].min()
    dates    = pd.Series(d.index.date, index=d.index)
    d["PDL"] = dates.map(day_low.shift(1, fill_value=float("nan")).to_dict())
    d["InSession"] = d.index.map(
        lambda x: (2 <= x.hour < 5) or (x.hour==9 and x.minute>=30) or (10 <= x.hour < 12))
    pc = close.shift(1)
    tr = pd.concat([high-low,(high-pc).abs(),(low-pc).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    d["HighVol"] = atr > 1.5 * atr.rolling(200).mean()
    d["DR"]    = d.groupby("Date")["High"].transform("max") - d.groupby("Date")["Low"].transform("min")
    d["AvgDR"] = d["Date"].map(d.groupby("Date")["DR"].first().rolling(14).mean())
    d["RangeOk"] = (d["DR"] >= d["AvgDR"]*0.6) & (d["DR"] <= d["AvgDR"]*1.4)
    d["DEMA50"]   = daily_ema(d, 50)
    d["DEMA200"]  = daily_ema(d, 200)
    d["DUptrend"] = (close > d["DEMA50"]) & (d["DEMA50"] > d["DEMA200"])
    d["Week"] = d.index.to_period("W")
    d["PWL"]  = d["Week"].map(d.groupby("Week")["Low"].min().shift(1).to_dict())
    base = d["InSession"] & d["DUptrend"] & ~d["HighVol"] & d["RangeOk"]
    d["Sig"] = 0
    d.loc[(low < d["AL"])  & (close > d["AL"])  & d["AL"].notna()  & base, "Sig"] = 1
    d.loc[(low < d["PDL"]) & (close > d["PDL"]) & d["PDL"].notna() & base, "Sig"] = 1
    d.loc[(low < d["PWL"]) & (close > d["PWL"]) & d["PWL"].notna() & base, "Sig"] = 1
    return d

s1 = compute_s1(qqq_h)
s2 = compute_s2(gld_h)
s4 = {"QQQ": compute_s4(qqq_h), "SPY": compute_s4(spy_h)}

print(f"  S1:{(s1['Sig']==1).sum()}  S2:L={(s2['Sig']==1).sum()}S={(s2['Sig']==-1).sum()}"
      f"  S3:{sum(v.sum() for v in s3_sig.values())}"
      f"  S4:{sum((s4[s]['Sig']==1).sum() for s in S4_SYMS)}")

# ── S5: 30-MIN ORB (pre-computed from 1-min data) ────────────────────────────
print("Loading 1-min data for S5...")
df1m = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_1min_7y.csv")
df1m["timestamp"] = pd.to_datetime(df1m["timestamp"], utc=True)
df1m = df1m.set_index("timestamp")
if "symbol" in df1m.columns: df1m = df1m[df1m["symbol"] == "QQQ"]
df1m.index = df1m.index.tz_convert(eastern)
df1m = df1m[["open","high","low","close","volume"]].copy()
df1m.columns = ["Open","High","Low","Close","Volume"]
df1m = df1m[(df1m.index.hour >= 9) & (df1m.index.hour < 16)]
df1m = df1m[~((df1m.index.hour == 9) & (df1m.index.minute < 30))]
df1m["Date"] = df1m.index.date
print(f"  RTH bars: {len(df1m):,}")

# 30-min ORB range: 9:30–9:59am (first 30 bars)
orb30  = df1m[df1m.index.hour == 9]
orb30_h = orb30.groupby("Date")["High"].max()
orb30_l = orb30.groupby("Date")["Low"].min()

# Normal-range filter: skip days where ORB range is abnormally wide (> 1.2x 20-day avg)
orb30_rng     = (orb30_h - orb30_l) / orb30_l   # as fraction of price
orb30_avg_rng = orb30_rng.rolling(20).mean().shift(1)
orb30_normal  = (orb30_rng < orb30_avg_rng * 1.2).to_dict()

df1m["ORBHigh"] = df1m["Date"].map(orb30_h)
df1m["ORBLow"]  = df1m["Date"].map(orb30_l)

# VIX + SPY maps for S5 (VIX 21d avg < 20 for all, SPY golden cross for longs)
_all_d1m = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(df1m["Date"].unique())])
_vix_s5  = vix_ma21.asof(_all_d1m);   _vix_s5.index  = [t.date() for t in _vix_s5.index]
_spy_s5  = spy_golden.asof(_all_d1m); _spy_s5.index  = [t.date() for t in _spy_s5.index]
vix_ok_s5   = (_vix_s5 < 20).to_dict()
spy_bull_s5 = _spy_s5.fillna(True).astype(bool).to_dict()

def precompute_s5():
    trades = {}
    for d, grp in df1m.groupby("Date"):
        if not vix_ok_s5.get(d, False): continue
        if not orb30_normal.get(d, True): continue   # skip wide-range open days
        orb_h = orb30_h.get(d); orb_l = orb30_l.get(d)
        if orb_h is None or orb_l is None or pd.isna(orb_h): continue
        spy_ok = spy_bull_s5.get(d, True)

        # Entry window: 10:00am–1pm (after ORB completes)
        win = grp[(grp.index.hour >= 10) & (grp.index.hour < 13)]
        direction = 0; entry_p = stop_p = target_p = entry_ts = None
        for ts, row in win.iterrows():
            c = float(row["Close"])
            if c > orb_h and spy_ok:
                direction=1; entry_p=c; entry_ts=ts
                stop_p=c*(1-STOP_S5); target_p=c*(1+STOP_S5*RR_S5); break
            elif c < orb_l:
                direction=-1; entry_p=c; entry_ts=ts
                stop_p=c*(1+STOP_S5); target_p=c*(1-STOP_S5*RR_S5); break

        if direction == 0: continue

        # Simulate 1-min exit
        exit_p = None
        for ts, row in grp[grp.index > entry_ts].iterrows():
            lo=float(row["Low"]); hi=float(row["High"])
            if direction==1:
                if lo <= stop_p:   exit_p=stop_p;   break
                if hi >= target_p: exit_p=target_p; break
            else:
                if hi >= stop_p:   exit_p=stop_p;   break
                if lo <= target_p: exit_p=target_p; break
            if ts.hour==15 and ts.minute>=55: exit_p=float(row["Close"]); break
        if exit_p is None: exit_p = float(grp.iloc[-1]["Close"])

        dt = pd.Timestamp(d)
        trades[d] = dict(dir=direction, entry_p=entry_p, exit_p=exit_p,
                         ppu=(exit_p-entry_p)*direction,
                         year=dt.year, month=dt.month)
    return trades

print("Pre-computing S5 trades...")
s5_trades = precompute_s5()
n5l = sum(1 for v in s5_trades.values() if v["dir"]==1)
n5s = sum(1 for v in s5_trades.values() if v["dir"]==-1)
print(f"  S5: {len(s5_trades)} trades  (long={n5l} short={n5s})")

# Shared hourly index
all_hrs = sorted(set(s1.index)|set(s2.index)|set(s4["QQQ"].index)|set(s4["SPY"].index))

# ── BACKTEST ENGINE ───────────────────────────────────────────────────────────
def run_master(use_vol_scaling=True, use_tsmom=True, include_s5=True, label="Full"):
    capital = INITIAL
    day_start = month_start = capital
    cur_day = cur_month = None
    day_risk = 0.0
    daily_locked = total_locked = monthly_locked = False

    def blank(): return dict(active=False,dir=0,entry=0.,stop=0.,target=0.,shares=0.)
    st1 = blank()
    st2 = blank()
    st3 = {s: dict(active=False,entry=0.,stop=0.,shares=0.,bars=0) for s in S3_SYMS}
    st3_pend = set()
    st4 = {s: blank() for s in S4_SYMS}
    s6 = dict(active=False, dir=0, entry=0., shares=0.)
    tlog = []
    eq_eod = {}

    for idx_i, ts in enumerate(all_hrs):
        bar_date  = ts.date()
        bar_month = (ts.year, ts.month)

        # Day / month resets
        if bar_date != cur_day:
            if cur_day is not None: eq_eod[cur_day] = capital
            cur_day = bar_date; day_start = capital; day_risk = 0.0; daily_locked = False
        if bar_month != cur_month:
            cur_month = bar_month; month_start = capital; monthly_locked = False

        # Kill switches
        if (capital-day_start)  / max(day_start,1)   <= -DAILY_LIMIT: daily_locked  = True
        if (capital-INITIAL)    / INITIAL             <= -DD_LIMIT:    total_locked  = True
        if (capital-month_start)/ max(month_start,1) >= MONTHLY_TGT:  monthly_locked = True
        can_enter = not (daily_locked or total_locked or monthly_locked)

        # Regime (SPY death cross only when NOT using TSMOM)
        regime = get_regime(bar_date, include_spy_dc=not use_tsmom)
        s14_ok = can_enter and regime == "normal"
        s23_ok = can_enter and regime != "halt"

        # TSMOM gate for S1/S4 (replaces SPY death cross)
        tsmom_global_mult = 1.0
        if use_tsmom:
            tsmom_val = tsmom_for(bar_date)
            if tsmom_val < 0:
                s14_ok = False               # skip new longs in S1/S4
                tsmom_global_mult = 0.5      # all other strategies at 50% size

        # Vol scaling multiplier (Barroso & Santa-Clara)
        vm = vol_mult_for(bar_date) if use_vol_scaling else 1.0
        combined_mult = vm * tsmom_global_mult

        is_first = (idx_i == 0 or all_hrs[idx_i-1].date() != bar_date)
        is_last  = (idx_i == len(all_hrs)-1 or all_hrs[idx_i+1].date() != bar_date)

        # ── S5 ORB at first bar of day ─────────────────────────────────────
        if is_first and include_s5 and can_enter and bar_date in s5_trades:
            t5 = s5_trades[bar_date]
            ep = t5["entry_p"]
            if regime != "halt" and ep > 0 and day_risk + RISK_S5 <= MAX_DAY_RISK:
                shrs = (capital * RISK_S5 * vm) / (ep * STOP_S5)   # vol scaling only (no TSMOM for S5)
                pnl  = shrs * t5["ppu"]
                capital += pnl
                tlog.append(dict(strategy="S5", sym="QQQ", year=ts.year,
                                 month=ts.month, pnl=pnl, entry_dt=ts))
                day_risk += RISK_S5

        # ── S6: SMA crossover at first bar of day ─────────────────────
        if is_first and s6_sig.get(bar_date, 0) != 0 and s14_ok and can_enter:
            direction = int(s6_sig[bar_date])
            o = s6_open.get(bar_date)
            if pd.notna(o) and o > 0:
                eff = 1.0 * combined_mult  # full exposure scaled by vol and tsmom
                shrs = (capital * eff) / o
                s6.update(active=True, dir=direction, entry=o, shares=shrs)

        # ── S3 entries at first bar ────────────────────────────────────────
        if is_first and s23_ok and st3_pend:
            dt_today = pd.Timestamp(bar_date)
            for sym in list(st3_pend):
                eff = RISK_S3 * combined_mult
                if not st3[sym]["active"] and day_risk + eff <= MAX_DAY_RISK:
                    if dt_today in daily[sym].index:
                        o = float(daily[sym].loc[dt_today, "Open"])
                        if not pd.isna(o) and o > 0:
                            st3[sym] = dict(active=True, entry=o,
                                            stop=o*(1-STOP_S3),
                                            shares=(capital*eff)/(o*STOP_S3), bars=0)
                            day_risk += eff
                st3_pend.discard(sym)

        # ── EXITS (always, regardless of lock) ────────────────────────────
        if st1["active"] and ts in s1.index:
            p = float(s1.loc[ts,"Close"])
            if p <= st1["stop"] or p >= st1["target"]:
                ep  = st1["stop"] if p <= st1["stop"] else st1["target"]
                pnl = st1["shares"] * (ep - st1["entry"]) * st1["dir"]
                capital += pnl
                tlog.append(dict(strategy="S1",sym="QQQ",year=ts.year,month=ts.month,
                                 pnl=pnl,entry_dt=ts))
                st1["active"] = False

        if st2["active"] and ts in s2.index:
            p = float(s2.loc[ts,"Close"]); dd2 = st2["dir"]
            hs = (dd2==1 and p<=st2["stop"]) or (dd2==-1 and p>=st2["stop"])
            ht = (dd2==1 and p>=st2["target"]) or (dd2==-1 and p<=st2["target"])
            if hs or ht:
                ep  = st2["stop"] if hs else st2["target"]
                pnl = st2["shares"] * (ep - st2["entry"]) * dd2
                capital += pnl
                tlog.append(dict(strategy="S2",sym="GLD",year=ts.year,month=ts.month,
                                 pnl=pnl,entry_dt=ts))
                st2["active"] = False

        for sym in S4_SYMS:
            st = st4[sym]
            if st["active"] and ts in s4[sym].index:
                p = float(s4[sym].loc[ts,"Close"])
                if p <= st["stop"] or p >= st["target"]:
                    ep  = st["stop"] if p <= st["stop"] else st["target"]
                    pnl = st["shares"] * (ep - st["entry"])
                    capital += pnl
                    tlog.append(dict(strategy="S4",sym=sym,year=ts.year,month=ts.month,
                                     pnl=pnl,entry_dt=ts))
                    st["active"] = False

        # ── S3 EOD exits + next-day signal queue ──────────────────────────
        if is_last:
            eq_eod[bar_date] = capital
            dt_today = pd.Timestamp(bar_date)
            for sym in S3_SYMS:
                st = st3[sym]
                if st["active"] and dt_today in daily[sym].index:
                    c = float(daily[sym].loc[dt_today,"Close"])
                    if pd.isna(c): continue
                    st["bars"] += 1
                    hit_stop = c <= st["stop"]
                    hit_time = st["bars"] >= HOLD_S3
                    if hit_stop or hit_time:
                        ep  = st["stop"] if hit_stop else c
                        pnl = st["shares"] * (ep - st["entry"])
                        capital += pnl
                        tlog.append(dict(strategy="S3",sym=sym,year=ts.year,month=ts.month,
                                         pnl=pnl,entry_dt=ts))
                        st["active"] = False
            if s23_ok:
                for sym in S3_SYMS:
                    if not st3[sym]["active"] and sym not in st3_pend:
                        if dt_today in s3_sig[sym].index and bool(s3_sig[sym].loc[dt_today]):
                            st3_pend.add(sym)

        # ── S6 EOD exit (close at day's close) ─────────────────────
        if is_last and s6["active"]:
            c = s6_close.get(bar_date)
            if pd.notna(c):
                pnl = s6["shares"] * (c - s6["entry"]) * s6["dir"]
                capital += pnl
                tlog.append(dict(strategy="S6", sym="QQQ", year=ts.year,
                                 month=ts.month, pnl=pnl, entry_dt=ts))
            s6.update(active=False, dir=0, entry=0., shares=0.)

        # ── ENTRIES ───────────────────────────────────────────────────────
        if not can_enter: continue

        if not st1["active"] and ts in s1.index and s14_ok:
            iloc = s1.index.get_loc(ts)
            if iloc > 0 and int(s1["Sig"].iloc[iloc-1]) == 1:
                eff = RISK_S1 * combined_mult
                if day_risk + eff <= MAX_DAY_RISK:
                    p = float(s1.loc[ts,"Close"])
                    st1.update(active=True,dir=1,entry=p,stop=p*(1-STOP_S1),
                               target=p*(1+STOP_S1*RR_S1),
                               shares=(capital*eff)/(p*STOP_S1))
                    day_risk += eff

        if not st2["active"] and ts in s2.index and s23_ok:
            iloc = s2.index.get_loc(ts)
            if iloc > 0:
                sig = int(s2["Sig"].iloc[iloc-1])
                if sig != 0:
                    eff = RISK_S2 * combined_mult
                    if day_risk + eff <= MAX_DAY_RISK:
                        p  = float(s2.loc[ts,"Close"])
                        sp = p*(1+STOP_S2) if sig==-1 else p*(1-STOP_S2)
                        tp = p*(1-STOP_S2*RR_S2) if sig==-1 else p*(1+STOP_S2*RR_S2)
                        st2.update(active=True,dir=sig,entry=p,stop=sp,target=tp,
                                   shares=(capital*eff)/(p*STOP_S2))
                        day_risk += eff

        for sym in S4_SYMS:
            st = st4[sym]
            if not st["active"] and ts in s4[sym].index and s14_ok:
                iloc = s4[sym].index.get_loc(ts)
                if iloc > 0 and int(s4[sym]["Sig"].iloc[iloc-1]) == 1:
                    eff = RISK_S4 * combined_mult
                    if day_risk + eff <= MAX_DAY_RISK:
                        p = float(s4[sym].loc[ts,"Close"])
                        st.update(active=True,dir=1,entry=p,stop=p*(1-STOP_S4),
                                  target=p*(1+STOP_S4*RR_S4),
                                  shares=(capital*eff)/(p*STOP_S4))
                        day_risk += eff

    eq_eod[cur_day] = capital

    tdf = pd.DataFrame(tlog) if tlog else pd.DataFrame(columns=["strategy","sym","year","month","pnl","entry_dt"])
    eq  = pd.Series(eq_eod).sort_index()
    eq.index = pd.to_datetime(eq.index)

    dr   = eq.pct_change().dropna()
    shrp = np.sqrt(252)*dr.mean()/dr.std() if dr.std()>0 else 0.0
    ea   = eq.values
    peak = np.maximum.accumulate(ea)
    mxdd = ((ea-peak)/peak).min() if len(ea)>1 else 0.0

    if len(tdf) and (tdf["pnl"]<0).any():
        pf = tdf.loc[tdf["pnl"]>0,"pnl"].sum() / abs(tdf.loc[tdf["pnl"]<0,"pnl"].sum())
    else:
        pf = float("inf")
    wr = (tdf["pnl"]>0).mean() if len(tdf) else 0.0

    eq_me  = eq.resample("ME").last()
    eq_ms  = eq_me.shift(1).fillna(INITIAL)
    mo_ret = (eq_me - eq_ms) / eq_ms

    return dict(
        label=label, capital=capital,
        ret=(capital-INITIAL)/INITIAL,
        max_dd=mxdd, sharpe=shrp, pf=pf, win_rate=wr,
        n_trades=len(tdf), tdf=tdf, eq=eq,
        monthly_ret=mo_ret,
        months_6pct=(mo_ret >= 0.06).sum(),
        months_loss=(mo_ret <  0.00).sum(),
        total_months=len(mo_ret),
    )

# ── RUN ALL VARIANTS ──────────────────────────────────────────────────────────
print("\nRunning comparison variants...")
variants = [
    ("Baseline",   False, False, False),
    ("+VolScale",  True,  False, False),
    ("+TSMOM",     False, True,  False),
    ("+ORB(S5)",   False, False, True),
    ("Full System",True,  True,  True),
]
results = {}
for label, vs, vt, v5 in variants:
    print(f"  {label}...")
    results[label] = run_master(vs, vt, v5, label)

# ── COMPARISON TABLE ──────────────────────────────────────────────────────────
n_yr = 7
print(f"\n{'═'*80}")
print("IMPROVEMENT COMPARISON  (target: avg/mo >2%, months ≥6% up, max DD <8%)")
print(f"{'═'*80}")
print(f"{'Label':<14} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>6} "
      f"{'Trades':>7} {'Avg/mo':>7} {'≥6%mo':>6} {'Lossmо':>7}")
print("-" * 80)
for label, *_ in variants:
    r = results[label]
    avg_mo = r["monthly_ret"].mean()
    dd_ok  = "✅" if r["max_dd"] > -0.08 else "❌"
    mo_ok  = "✅" if avg_mo > 0.02 else "❌"
    print(f"{label:<14} {r['ret']:>+7.1%} {r['max_dd']:>6.1%}{dd_ok} "
          f"{r['sharpe']:>6.2f} {r['pf']:>5.2f} "
          f"{r['n_trades']:>7} {avg_mo:>+6.2%}{mo_ok} "
          f"{r['months_6pct']:>5}/{r['total_months']} "
          f"{r['months_loss']:>5}mo")

# ── DETAILED STATS: FULL SYSTEM ───────────────────────────────────────────────
r = results["Full System"]
tdf = r["tdf"]
eq  = r["eq"]
mo  = r["monthly_ret"]
all_yrs = sorted(tdf["year"].unique()) if len(tdf) else []
strats  = ["S1","S2","S3","S4","S5","S6"]

print(f"\n{'═'*60}")
print("FULL SYSTEM — DETAILED RESULTS")
print(f"{'═'*60}")
print(f"  Return:        {r['ret']:+.1%}  (${r['capital']-INITIAL:,.0f})")
print(f"  Final capital: ${r['capital']:,.2f}")
print(f"  Max drawdown:  {r['max_dd']:.1%}  {'✅' if r['max_dd']>-0.08 else '❌'}")
print(f"  Sharpe ratio:  {r['sharpe']:.2f}")
print(f"  Profit factor: {r['pf']:.2f}")
print(f"  Win rate:      {r['win_rate']:.0%}")
print(f"  Total trades:  {r['n_trades']}  ({r['n_trades']/n_yr:.1f}/yr)")

print(f"\n  Monthly distribution ({r['total_months']} months):")
print(f"    ≥ 6% months:    {r['months_6pct']}  ({r['months_6pct']/r['total_months']:.0%})")
print(f"    ≥ 2% months:    {(mo>=0.02).sum()}  ({(mo>=0.02).mean():.0%})")
print(f"    Positive months:{(mo>=0.00).sum()}  ({(mo>=0.00).mean():.0%})")
print(f"    Loss months:    {r['months_loss']}  ({r['months_loss']/r['total_months']:.0%})")
print(f"    Avg monthly:    {mo.mean():+.2%}  (target >2%)")
print(f"    Best month:     {mo.max():+.2%}")
print(f"    Worst month:    {mo.min():+.2%}")

print(f"\n  Projected income (avg {mo.mean():.2%}/month):")
for acct in [10_000, 50_000, 100_000]:
    print(f"    ${acct:>7,}: ${acct*mo.mean():>6,.0f}/month  |  ${acct*r['ret']/n_yr:>7,.0f}/year")

print(f"\n{'─'*60}")
print("PER-STRATEGY BREAKDOWN")
print(f"{'─'*60}")
for s in strats:
    sub = tdf[tdf["strategy"]==s]
    if len(sub)==0: print(f"  {s}: no trades"); continue
    sp  = sub["pnl"]
    spf = sp[sp>0].sum()/abs(sp[sp<0].sum()) if (sp<0).any() else float("inf")
    print(f"  {s}: {len(sub):>4} trades  WR:{(sp>0).mean():.0%}  "
          f"PF:{spf:.2f}  P&L:${sp.sum():+,.0f}  ({len(sub)/n_yr:.1f}/yr)")

print(f"\n{'─'*60}")
print("YEAR-BY-YEAR P&L PER STRATEGY ($)")
print(f"{'─'*60}")
hdr = f"{'Year':<6}" + "".join(f"  {s:>7}" for s in strats) + "     Total"
print(hdr); print("-" * len(hdr))
for yr in all_yrs:
    row = f"{yr:<6}"; tot = 0
    for s in strats:
        sub = tdf[(tdf["strategy"]==s)&(tdf["year"]==yr)]
        p = sub["pnl"].sum() if len(sub) else 0; tot += p
        row += f"  {p:>+7,.0f}"
    print(row + f"  {tot:>+8,.0f}")

print(f"\n{'─'*60}")
print("MONTHLY RETURNS — FULL SYSTEM (last 24 months)")
print(f"{'─'*60}")
recent_cut = sorted(tdf["year"].unique())[-2] if len(all_yrs)>=2 else all_yrs[0]
recent = tdf[tdf["year"] >= recent_cut]
mp = recent.groupby(["year","month","strategy"])["pnl"].sum().unstack(fill_value=0)
mt = recent.groupby(["year","month"])["pnl"].sum()
print(f"{'YM':<8}" + "".join(f"  {s:>7}" for s in strats) + "     Total     Ret%")
print("-" * 65)
for (yr,mo_n) in sorted(mt.index):
    ym = f"{yr}-{str(mo_n).zfill(2)}"; row = f"{ym:<8}"
    for s in strats:
        v = mp.loc[(yr,mo_n),s] if (yr,mo_n) in mp.index and s in mp.columns else 0
        row += f"  {v:>+7,.0f}"
    tot = mt.loc[(yr,mo_n)]
    ts_end = pd.Timestamp(f"{yr}-{str(mo_n).zfill(2)}-01") + pd.offsets.MonthEnd(0)
    mo_pct = mo.iloc[mo.index.get_indexer([ts_end], method="nearest")[0]] if len(mo) else float("nan")
    ret_s  = f"{mo_pct:>+6.1%}" if not pd.isna(mo_pct) else "   n/a"
    print(row + f"  {tot:>+8,.0f}  {ret_s}")

# ── CHARTS ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16,13))
gs  = GridSpec(3,2,figure=fig,hspace=0.42,wspace=0.30)
colors = {"S1":"#4c78a8","S2":"#f58518","S3":"#54a24b","S4":"#e45756","S5":"#9467bd","S6":"#8c564b"}

# 1. Equity curves: all 5 variants
ax1 = fig.add_subplot(gs[0,:])
line_styles = ["-","--","-.",":",(0,(3,1,1,1))]
for (label,*_), ls in zip(variants, line_styles):
    rv = results[label]
    eq_v = rv["eq"]
    ax1.plot(eq_v.index, eq_v.values, linestyle=ls, linewidth=1.3,
             label=f"{label}  Ret:{rv['ret']:+.0%}  DD:{rv['max_dd']:.1%}")
ax1.axhline(INITIAL*0.92, color="red", linestyle="--", linewidth=0.8, alpha=0.5, label="8% DD limit")
ax1.set_title("All Variants — Equity Curves", fontsize=10)
ax1.set_ylabel("Capital ($)"); ax1.legend(fontsize=7.5); ax1.grid(True,alpha=0.3)

# 2. Monthly returns bar — Full System
ax2 = fig.add_subplot(gs[1,0])
mo_full = results["Full System"]["monthly_ret"]
mc = ["#2ca02c" if v>=0.06 else "#98df8a" if v>=0 else "#d62728" for v in mo_full.values]
ax2.bar(range(len(mo_full)), mo_full.values*100, color=mc, width=0.85)
ax2.axhline(6, color="gold", linestyle="--", linewidth=1.0, label="6% target")
ax2.axhline(0, color="black", linewidth=0.5)
n6 = (mo_full>=0.06).sum()
ax2.set_title(f"Full System Monthly Returns  |  {n6}/{len(mo_full)} months ≥6%  |  "
              f"avg {mo_full.mean():.2%}", fontsize=9)
ax2.set_ylabel("%"); ax2.legend(fontsize=8); ax2.grid(True,alpha=0.3,axis="y")

# 3. Per-strategy cumulative P&L — Full System
ax3 = fig.add_subplot(gs[1,1])
for s in strats:
    sub = tdf[tdf["strategy"]==s].copy().sort_values("entry_dt")
    if len(sub)==0: continue
    cum = sub["pnl"].cumsum()
    ax3.plot(sub["entry_dt"].values, cum.values, label=s, color=colors[s], linewidth=1.1)
ax3.axhline(0,color="black",linewidth=0.5)
ax3.set_title("Cumulative P&L by Strategy — Full System", fontsize=9)
ax3.set_ylabel("P&L ($)"); ax3.legend(fontsize=8); ax3.grid(True,alpha=0.3)

# 4. Year-by-year stacked bar — Full System
ax4 = fig.add_subplot(gs[2,0])
bottoms = np.zeros(len(all_yrs))
for s in strats:
    vals = np.array([tdf[(tdf["strategy"]==s)&(tdf["year"]==yr)]["pnl"].sum()
                     for yr in all_yrs])
    ax4.bar(all_yrs, vals, bottom=bottoms, label=s, color=colors[s], alpha=0.85)
    bottoms += vals
ax4.axhline(0,color="black",linewidth=0.5)
ax4.set_title("Year-by-Year P&L by Strategy", fontsize=9)
ax4.set_ylabel("P&L ($)"); ax4.legend(fontsize=8); ax4.grid(True,alpha=0.3,axis="y")

# 5. Vol scaling multiplier over time
ax5 = fig.add_subplot(gs[2,1])
vm_ts = _vol_mult.dropna()
ax5.plot(vm_ts.index, vm_ts.values, color="#333333", linewidth=0.8)
ax5.axhline(1.0, color="blue",  linestyle="--", linewidth=0.8, alpha=0.6, label="1× (base)")
ax5.axhline(2.0, color="green", linestyle="--", linewidth=0.8, alpha=0.5, label="2× cap")
ax5.axhline(0.25,color="red",   linestyle="--", linewidth=0.8, alpha=0.5, label="0.25× floor")
ax5.fill_between(vm_ts.index, vm_ts.values, 1.0,
                 where=vm_ts.values>1, alpha=0.12, color="green")
ax5.fill_between(vm_ts.index, vm_ts.values, 1.0,
                 where=vm_ts.values<1, alpha=0.15, color="red")
ax5.set_title("Vol Scaling Multiplier (target=12% ann. vol)", fontsize=9)
ax5.set_ylabel("Size multiplier"); ax5.legend(fontsize=8); ax5.grid(True,alpha=0.3)

fig.suptitle(
    "Master Backtest — 5 Strategies + Vol Scaling (B&SC 2015) + TSMOM (MOP 2012) + 5-min ORB",
    fontsize=11, fontweight="bold")
out = "/Users/colindayer/nas100_backtest/equity_master.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nChart saved: {out}")
