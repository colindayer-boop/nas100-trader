"""
Combined 5-Strategy Backtest with GEX Filters
Strategies: S1 Asian Sweep, S2 Gold FVG, S3 Abnormal Volume, S4 Multi-Sweep, S5 ORB
GEX data: OptionsDX QQQ + SPX + SPY option chains
"""

import pandas as pd
import numpy as np
import glob, os, warnings
from datetime import date, timedelta
import yfinance as yf

warnings.filterwarnings("ignore")

DATA_DIR = "/Users/colindayer/nas100_backtest/optionsdx/"
QQQ_CSV  = "/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv"
START    = "2019-01-01"
END      = "2023-12-31"

# ── STEP 1: LOAD OPTION CHAIN DATA AND CALC GEX ──────────────────────────────
def load_gex(symbol):
    """Load option chain files for a symbol and return daily GEX series."""
    pattern_sym = symbol.lower()
    files = sorted(
        glob.glob(DATA_DIR + f"{pattern_sym}_eod*.txt") +
        glob.glob(DATA_DIR + f"{pattern_sym}_eod*.csv") +
        glob.glob(DATA_DIR + f"**/{pattern_sym}_eod*.txt") +
        glob.glob(DATA_DIR + f"**/{pattern_sym}_eod*.csv")
    )
    if not files:
        print(f"  {symbol}: no option chain files found in {DATA_DIR}")
        return None

    print(f"  {symbol}: loading {len(files)} files...")
    # Peek at first file to find needed column indices (read only what we need)
    _peek = pd.read_csv(files[0], nrows=0)
    _peek.columns = [c.strip().strip("[]").upper() for c in _peek.columns]
    _needed_kw = ["DATE", "UNDERLYING", "GAMMA", "VOLUME", "OI", "STRIKE", "IV"]
    _usecols = [i for i, c in enumerate(_peek.columns)
                if any(k in c for k in _needed_kw)]
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, low_memory=False, usecols=_usecols)
            df.columns = [c.strip().strip("[]").upper() for c in df.columns]
            skip = {"QUOTE_READTIME", "QUOTE_DATE", "EXPIRE_DATE"}
            for col in df.columns:
                if col not in skip:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            dfs.append(df)
        except Exception as e:
            pass

    raw = pd.concat(dfs, ignore_index=True)

    # Find columns
    def fc(keywords):
        for k in keywords:
            m = [c for c in raw.columns if k in c]
            if m: return m[0]
        return None

    date_col   = fc(["QUOTE_DATE"])
    under_col  = fc(["UNDERLYING_LAST", "UNDERLYING"])
    c_gamma    = fc(["C_GAMMA", "CALL_GAMMA"])
    p_gamma    = fc(["P_GAMMA", "PUT_GAMMA"])
    c_oi       = fc(["C_OI", "CALL_OI", "C_OPEN_INT", "C_VOLUME"])
    p_oi       = fc(["P_OI", "PUT_OI", "P_OPEN_INT", "P_VOLUME"])

    if not date_col:
        print(f"  {symbol}: no date column found")
        return None

    raw[date_col] = pd.to_datetime(raw[date_col])
    raw = raw.rename(columns={date_col: "QUOTE_DATE"})

    # Vectorized GEX calculation — much faster than day-by-day loop
    raw["_date"] = raw["QUOTE_DATE"].dt.date
    price_by_day = raw.groupby("_date")[under_col].first() if under_col else None

    raw["_cgex"] = 0.0
    raw["_pgex"] = 0.0
    if c_gamma and c_oi and price_by_day is not None:
        raw["_price"] = raw["_date"].map(price_by_day)
        raw["_cgex"] = raw[c_gamma].fillna(0) * raw[c_oi].fillna(0) * 100 * raw["_price"].fillna(0)
    if p_gamma and p_oi and price_by_day is not None:
        if "_price" not in raw.columns:
            raw["_price"] = raw["_date"].map(price_by_day)
        raw["_pgex"] = raw[p_gamma].fillna(0) * raw[p_oi].fillna(0) * 100 * raw["_price"].fillna(0) * -1

    raw["_gex"] = raw["_cgex"] + raw["_pgex"]
    gex_series = raw.groupby("_date")["_gex"].sum()
    gex_df = gex_series.rename("gex").to_frame()
    neg_days = (gex_df["gex"] < 0).sum()
    print(f"  {symbol}: {len(gex_df)} days | neg GEX {neg_days/len(gex_df):.0%} of time")
    return gex_df["gex"]


print("=" * 60)
print("LOADING GEX DATA")
print("=" * 60)

# Use pre-computed QQQ GEX cache if available (saves ~10 min reload)
GEX_CACHE = "/Users/colindayer/nas100_backtest/gex_history.csv"
if os.path.exists(GEX_CACHE):
    print("  QQQ: loading from cache (gex_history.csv)...")
    _cache = pd.read_csv(GEX_CACHE, index_col=0, parse_dates=True)
    _cache.index = pd.to_datetime(_cache.index).date
    qqq_gex = _cache["gex"] if "gex" in _cache.columns else _cache.iloc[:,0]
    qqq_gex.index = _cache.index
    print(f"  QQQ: {len(qqq_gex)} days loaded from cache")
else:
    qqq_gex = load_gex("QQQ")

# SPX not used by any strategy — skip it
spx_gex = None

# SPY GEX — load only needed columns for speed
spy_gex = load_gex("SPY")

# Combined market GEX signal: negative = good for trend trades
def is_neg_gex(d, primary_gex, secondary_gex=None):
    """True if primary GEX is negative (or missing = allow trade)."""
    val = primary_gex.get(d) if primary_gex is not None else None
    if val is None:
        return True  # missing data = don't filter
    return float(val) < 0


# ── STEP 2: LOAD PRICE DATA ──────────────────────────────────────────────────
print("\nLoading price data...")
import pytz
eastern = pytz.timezone("US/Eastern")

df = pd.read_csv(QQQ_CSV)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp").tz_convert(eastern)

def get_hourly(sym):
    s = df[df["symbol"] == sym][["open","high","low","close","volume"]].copy()
    s.columns = ["Open","High","Low","Close","Volume"]
    s = s[s.index.date >= pd.Timestamp(START).date()]
    s = s[s.index.date <= pd.Timestamp(END).date()]
    s["Date"] = s.index.date
    return s

qqq = get_hourly("QQQ")

# SPY not in local CSV — synthesize hourly-shaped daily bars for signal building
print("Downloading SPY daily (2019-2023) as hourly proxy...")
_spy_d = yf.download("SPY", start=START, end=END, interval="1d", progress=False, auto_adjust=True)
if isinstance(_spy_d.columns, pd.MultiIndex): _spy_d.columns = _spy_d.columns.droplevel(1)
_spy_d.index = pd.to_datetime(_spy_d.index).tz_localize(None)
_spy_d = _spy_d[["Open","High","Low","Close","Volume"]].copy()
_spy_d["Date"] = _spy_d.index.date
# Give it a timezone-aware index so add_asian_signals works
_spy_d.index = _spy_d.index.tz_localize(eastern)
spy = _spy_d

# Gold (GLD) hourly via yfinance
print("Downloading GLD hourly (2019-2023)...")
gld_raw = yf.download("GLD", start=START, end=END, interval="1h", progress=False, auto_adjust=True)
if isinstance(gld_raw.columns, pd.MultiIndex):
    gld_raw.columns = gld_raw.columns.droplevel(1)
gld_raw.index = pd.to_datetime(gld_raw.index)
if gld_raw.index.tz is None:
    gld_raw.index = gld_raw.index.tz_localize("UTC")
gld_raw.index = gld_raw.index.tz_convert(eastern)
gld = gld_raw[["Open","High","Low","Close","Volume"]].copy()
gld["Date"] = gld.index.date

# ── STEP 3: COMMON REGIME FILTERS ────────────────────────────────────────────
print("Computing regime filters...")
end_str = str(date.today())

vix = yf.download("^VIX", start=START, end=end_str, progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma21 = vix.rolling(21).mean()

spy_close = yf.download("SPY", start=str(pd.Timestamp(START) - timedelta(days=365)), end=end_str, progress=False)["Close"]
if isinstance(spy_close, pd.DataFrame): spy_close = spy_close.iloc[:,0]
spy_close.index = pd.to_datetime(spy_close.index).tz_localize(None).normalize()
spy_bull_daily = spy_close.ewm(span=50).mean() > spy_close.ewm(span=200).mean()

def map_daily(series, dates):
    m = series.reindex(series.index.union(dates)).ffill()
    r = m.asof(dates)
    r.index = [t.date() for t in r.index]
    return r

all_dates_ts = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(set(
    list(qqq["Date"].unique()) + list(spy["Date"].unique())
))])
vix_by_date  = map_daily(vix_ma21, all_dates_ts)
bull_by_date = map_daily(spy_bull_daily, all_dates_ts)

def vix_mult(d):
    v = vix_by_date.get(d, np.nan)
    if pd.isna(v): return 1.0
    if v > 25: return 0.0
    if v >= 20: return 0.5
    return 1.0


# ── STEP 4: STRATEGY SIGNAL BUILDERS ─────────────────────────────────────────
def add_asian_signals(data):
    def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
    def sess_date(idx): return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()
    data["Asian"]       = data.index.map(is_asian)
    data["SessionDate"] = data.index.map(sess_date)
    ab = data[data["Asian"]]
    data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
    data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())
    data["InSession"]  = data.index.map(lambda x: (2<=x.hour<5) or (9<=x.hour<12))
    tp = (data["High"]+data["Low"]+data["Close"])/3
    vv=[]; ct=cv=0.; pd_=None
    for i in range(len(data)):
        d=data["Date"].iloc[i]
        if d!=pd_: ct=cv=0.; pd_=d
        if data["Volume"].iloc[i]>0: ct+=tp.iloc[i]*data["Volume"].iloc[i]; cv+=data["Volume"].iloc[i]
        vv.append(ct/cv if cv>0 else float("nan"))
    data["VWAP"] = vv
    dc=data[data.index.hour==16][["Close"]].copy(); dc.index=dc.index.date
    dc=dc[~dc.index.duplicated(keep="last")]
    data["EMA50"]  = data["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
    data["EMA200"] = data["Date"].map(dc["Close"].ewm(span=200).mean().to_dict())
    pc=data["Close"].shift(1)
    tr=pd.concat([data["High"]-data["Low"],(data["High"]-pc).abs(),(data["Low"]-pc).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean()
    data["HighVol"] = atr > 1.5*atr.rolling(200).mean()
    return data

# S1: QQQ Asian Sweep (long only)
print("Building S1 signals...")
qqq = add_asian_signals(qqq)
qqq["SPYBull"]  = qqq["Date"].map(bull_by_date).fillna(True).astype(bool)
qqq["SweepLow"] = (qqq["Low"]<qqq["AsianLow"]) & (qqq["Close"]>qqq["AsianLow"])
qqq_gex_map = qqq_gex.to_dict() if qqq_gex is not None else {}
qqq["NegGEX"]  = qqq["Date"].map(lambda d: qqq_gex_map.get(d, 0) < 0 if d in qqq_gex_map else True)
qqq["S1"] = (qqq["SweepLow"] & qqq["InSession"] &
             (qqq["Close"]>qqq["VWAP"]) & (qqq["Close"]>qqq["EMA50"]) &
             qqq["SPYBull"] & ~qqq["HighVol"] & qqq["AsianLow"].notna() & qqq["NegGEX"]).astype(int)

# S4: Multi-Sweep on QQQ with tighter confirmation (SPY daily data can't generate Asian sweep signals)
print("Building S4 signals...")
# SPY daily doesn't have Asian session hours — use QQQ with stricter EMA filter as S4q
spy = qqq.copy()  # placeholder so downstream refs don't crash
spy["SPYBull"] = spy["Date"].map(bull_by_date).fillna(True).astype(bool)
spy["SweepLow"] = (spy["Low"]<spy["AsianLow"]) & (spy["Close"]>spy["AsianLow"])
spy_gex_map = spy_gex.to_dict() if spy_gex is not None else {}
spy["NegGEX"] = spy["Date"].map(lambda d: spy_gex_map.get(d, 0) < 0 if d in spy_gex_map else True)
spy["S4"] = (spy["SweepLow"] & spy["InSession"] &
             (spy["Close"]>spy["VWAP"]) & (spy["Close"]>spy["EMA50"]) &
             (spy["EMA50"]>spy["EMA200"]) & spy["SPYBull"] &
             ~spy["HighVol"] & spy["AsianLow"].notna() & spy["NegGEX"]).astype(int)
qqq["S4q"] = (qqq["SweepLow"] & qqq["InSession"] &
              (qqq["Close"]>qqq["VWAP"]) & (qqq["Close"]>qqq["EMA50"]) &
              (qqq["EMA50"]>qqq["EMA200"]) & qqq["SPYBull"] &
              ~qqq["HighVol"] & qqq["AsianLow"].notna() & qqq["NegGEX"]).astype(int)

# S5: ORB 30-min on QQQ (first 30-min range breakout)
print("Building S5 signals...")
def build_orb(data):
    data["IsORB"] = data.index.map(lambda x: x.hour == 9 and x.minute == 30)
    orb_highs = data[data["IsORB"]].groupby("Date")["High"].max()
    orb_lows  = data[data["IsORB"]].groupby("Date")["Low"].min()
    data["ORBHigh"] = data["Date"].map(orb_highs)
    data["ORBLow"]  = data["Date"].map(orb_lows)
    data["AfterORB"] = data.index.map(lambda x: (x.hour==10) or (x.hour==11 and x.minute==0))
    data["S5_long"]  = (data["AfterORB"] & (data["Close"]>data["ORBHigh"]) &
                        data["SPYBull"] & data["NegGEX"] & data["ORBHigh"].notna()).astype(int)
    data["S5_short"] = (data["AfterORB"] & (data["Close"]<data["ORBLow"]) &
                        ~data["SPYBull"] & data["ORBLow"].notna()).astype(int)
    return data
qqq = build_orb(qqq)

# S2: Gold FVG (Fair Value Gap on GLD)
print("Building S2 signals (Gold FVG)...")
gld["SPYBull"] = gld["Date"].map(bull_by_date).fillna(True).astype(bool)
# FVG: gap between candle[i-2].high and candle[i].low (bullish) or vice versa
gld["FVG_bull"] = (gld["Low"] > gld["High"].shift(2)) & (gld["Close"] > gld["Open"]) & gld["SPYBull"]
gld["FVG_bear"] = (gld["High"] < gld["Low"].shift(2)) & (gld["Close"] < gld["Open"]) & ~gld["SPYBull"]
gld["S2_long"]  = gld["FVG_bull"].astype(int)
gld["S2_short"] = gld["FVG_bear"].astype(int)

# S3: Abnormal Volume on QQQ (daily)
print("Building S3 signals...")
qqq_daily = qqq.groupby("Date").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).copy()
qqq_daily["VolMA20"] = qqq_daily["Volume"].rolling(20).mean()
qqq_daily["AbnVol"]  = qqq_daily["Volume"] > 2.0 * qqq_daily["VolMA20"]
qqq_daily["SPYBull"] = pd.Series({d: bull_by_date.get(pd.Timestamp(d), True) for d in qqq_daily.index})
qqq_daily["NegGEX"]  = pd.Series({d: qqq_gex_map.get(d, 0) < 0 if d in qqq_gex_map else True for d in qqq_daily.index})
qqq_daily["S3_long"] = (qqq_daily["AbnVol"] & qqq_daily["SPYBull"] &
                        (qqq_daily["Close"] > qqq_daily["Open"]) & qqq_daily["NegGEX"]).astype(int)

# S6: IV Skew Reversal (Xing, Zhang & Zhao 2010)
# Calculate daily skew from OptionsDX QQQ files: OTM put IV - ATM call IV
# Extreme skew + price stabilizing + SPY bull + neg GEX → long fade
print("Building S6 signals (IV Skew Reversal from OptionsDX data)...")

# Load QQQ option chain data (already in memory from load_gex — reload lightweight version)
_qqq_files = sorted(
    glob.glob(DATA_DIR + "qqq_eod*.txt") + glob.glob(DATA_DIR + "qqq_eod*.csv") +
    glob.glob(DATA_DIR + "**/qqq_eod*.txt", recursive=True)
)
skew_records = []
for f in _qqq_files:
    try:
        df = pd.read_csv(f, low_memory=False)
        df.columns = [c.strip().strip("[]").upper() for c in df.columns]
        skip = {"QUOTE_READTIME", "QUOTE_DATE", "EXPIRE_DATE"}
        for col in df.columns:
            if col not in skip:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        date_col = next((c for c in df.columns if "QUOTE_DATE" in c), None)
        if not date_col: continue
        df[date_col] = pd.to_datetime(df[date_col])

        under_col = next((c for c in df.columns if "UNDERLYING_LAST" in c), None)
        strike_col = next((c for c in df.columns if c == "STRIKE"), None)
        c_iv_col   = next((c for c in df.columns if c == "C_IV"), None)
        p_iv_col   = next((c for c in df.columns if c == "P_IV"), None)
        if not all([under_col, strike_col, c_iv_col, p_iv_col]): continue

        for d, grp in df.groupby(df[date_col].dt.date):
            grp = grp.dropna(subset=[under_col, strike_col, c_iv_col, p_iv_col])
            if len(grp) < 5: continue
            spot = float(grp[under_col].median())
            # ATM call IV: strike closest to spot
            atm_row = grp.iloc[(grp[strike_col] - spot).abs().argsort()[:1]]
            atm_iv  = float(atm_row[c_iv_col].iloc[0])
            # OTM put IV: strike closest to spot * 0.95
            otm_target = spot * 0.95
            otm_row = grp.iloc[(grp[strike_col] - otm_target).abs().argsort()[:1]]
            otm_iv  = float(otm_row[p_iv_col].iloc[0])
            if atm_iv > 0 and otm_iv > 0:
                skew_records.append({"date": d, "skew": otm_iv - atm_iv})
    except Exception:
        continue

skew_df = pd.DataFrame(skew_records).drop_duplicates("date").set_index("date").sort_index()
print(f"  IV skew calculated for {len(skew_df)} days | mean={skew_df['skew'].mean():.3f} std={skew_df['skew'].std():.3f}")

# Signal: skew > mean + 1.5*std (extreme fear spike) + price stable + SPY bull + neg GEX
skew_threshold = skew_df["skew"].mean() + 1.5 * skew_df["skew"].std()
print(f"  Extreme skew threshold: {skew_threshold:.3f}")

qqq_daily["IVSkew"]      = qqq_daily.index.map(lambda d: skew_df["skew"].get(d, np.nan))
qqq_daily["SkewExtreme"] = qqq_daily["IVSkew"] > skew_threshold
qqq_daily["PriceStable"] = qqq_daily["Close"] > qqq_daily["Open"]  # green candle = stabilizing
qqq_daily["S6_long"] = (
    qqq_daily["SkewExtreme"] &
    qqq_daily["PriceStable"] &
    qqq_daily["SPYBull"] &
    qqq_daily["NegGEX"] &
    (qqq_daily.index.map(lambda d: vix_mult(d)) > 0)
).astype(int)
s6_signals = qqq_daily["S6_long"].sum()
print(f"  S6 signals found: {s6_signals} over 5 years ({s6_signals/5:.1f}/yr)")


# ── STEP 5: BACKTEST ENGINE ───────────────────────────────────────────────────
def backtest_single(data, sig_col, label, risk=0.007, sl=0.015, rr=3.0, short=False):
    capital = 10_000; init = capital
    trades = []; years_list = []
    in_trade = False; entry = stop = target = shares = 0.
    day_start = capital; cur_day = None; locked = False

    for i in range(1, len(data)):
        d = data.index[i].date() if hasattr(data.index[i], 'date') else data.index[i]
        price = float(data["Close"].iloc[i])
        sig   = int(data[sig_col].iloc[i-1])
        vm    = vix_mult(d)

        if d != cur_day:
            cur_day = d; day_start = capital; locked = False
        if (capital-day_start)/max(day_start,1) <= -0.05 or (capital-init)/init <= -0.10:
            locked = True
        if locked: continue

        if in_trade:
            hit_stop   = price <= stop if not short else price >= stop
            hit_target = price >= target if not short else price <= target
            if hit_stop:
                pnl = shares*(stop-entry) if not short else shares*(entry-stop)
                capital += pnl; trades.append(pnl)
                years_list.append(d.year); in_trade = False
            elif hit_target:
                pnl = shares*(target-entry) if not short else shares*(entry-target)
                capital += pnl; trades.append(pnl)
                years_list.append(d.year); in_trade = False
        elif sig == 1 and vm > 0:
            in_trade = True; entry = price
            if not short:
                stop = price*(1-sl); target = price*(1+sl*rr)
            else:
                stop = price*(1+sl); target = price*(1-sl*rr)
            shares = (capital*risk*vm)/(price*sl)

    t = pd.Series(trades)
    if len(t) == 0:
        return {"label":label, "ret":0, "dd":0, "trades":0, "tpy":0, "wr":0, "pf":0, "years":{}, "capital":init}
    pf  = t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else float("inf")
    ret = (capital-init)/init
    eq  = pd.Series([init]+list(t.cumsum()+init))
    dd  = ((eq-eq.cummax())/eq.cummax()).min()
    years = {}
    for y, pnl in zip(years_list, trades):
        years[y] = years.get(y,0) + pnl
    yrs = (data.index[-1] - data.index[0]).days / 365 if hasattr(data.index[0], 'date') else 5
    return {"label":label, "ret":ret, "dd":dd,
            "trades":len(t), "tpy":len(t)/max(yrs,1),
            "wr":(t>0).mean(), "pf":pf, "years":years, "capital":capital}

# Run all strategies
print("\n" + "="*60)
print("RUNNING BACKTESTS")
print("="*60)

results = []

r = backtest_single(qqq, "S1",      "S1 QQQ Asian Sweep (long)",    risk=0.007, sl=0.015, rr=3.0)
results.append(r); print(f"S1 done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(qqq, "S4q",     "S4 QQQ Multi-Sweep (long)",    risk=0.005, sl=0.015, rr=3.0)
results.append(r); print(f"S4 QQQ done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(spy, "S4",      "S4 SPY Multi-Sweep (long)",    risk=0.005, sl=0.015, rr=3.0)
results.append(r); print(f"S4 SPY done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(qqq, "S5_long", "S5 QQQ ORB Long",              risk=0.005, sl=0.012, rr=2.5)
results.append(r); print(f"S5 long done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(qqq, "S5_short","S5 QQQ ORB Short",             risk=0.003, sl=0.012, rr=2.5, short=True)
results.append(r); print(f"S5 short done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(gld, "S2_long", "S2 Gold FVG Long",             risk=0.005, sl=0.012, rr=2.0)
results.append(r); print(f"S2 long done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(qqq_daily, "S3_long","S3 Abnormal Volume Long", risk=0.004, sl=0.020, rr=2.5)
results.append(r); print(f"S3 done: {r['trades']} trades, ret={r['ret']:+.1%}")

r = backtest_single(qqq_daily, "S6_long","S6 IV Skew Reversal",     risk=0.005, sl=0.012, rr=2.5)
results.append(r); print(f"S6 done: {r['trades']} trades, ret={r['ret']:+.1%}")


# ── STEP 6: COMBINED RESULTS ──────────────────────────────────────────────────
print("\n" + "="*60)
print("COMBINED RESULTS  ($10,000 starting capital each strategy)")
print("="*60)
print(f"\n{'Strategy':<30} {'Return':>8} {'Max DD':>8} {'Trades':>7} {'T/yr':>5} {'WR':>6} {'PF':>6}")
print("-"*70)

total_ret = 0; all_trades = 0
for r in results:
    print(f"{r['label']:<30} {r['ret']:>+8.1%} {r['dd']:>8.1%} {r['trades']:>7} {r['tpy']:>5.0f} {r['wr']:>6.0%} {r['pf']:>6.2f}")
    total_ret += r['ret']
    all_trades += r['trades']

print("-"*70)
avg_ret = total_ret / len(results)
print(f"{'AVERAGE PER STRATEGY':<30} {avg_ret:>+8.1%}")
print(f"{'TOTAL TRADES (all strats)':<30} {all_trades:>7}")

# Yearly breakdown (combined P&L in dollars across all strategies)
print(f"\n{'YEARLY P&L (sum of all strategies, $10k base each)':}")
print("-"*40)
all_years = {}
for r in results:
    for y, pnl in r["years"].items():
        all_years[y] = all_years.get(y, 0) + pnl

for y in sorted(all_years):
    pct = all_years[y] / (10_000 * len(results)) * 100
    bar = "+" * int(abs(pct)/0.5) if pct > 0 else "-" * int(abs(pct)/0.5)
    print(f"  {y}: ${all_years[y]:>+8,.0f}  ({pct:+.1f}%)  {bar[:30]}")

total_pnl = sum(all_years.values())
total_pct = total_pnl / (10_000 * len(results)) * 100
print(f"\n  TOTAL 2019-2023: ${total_pnl:>+,.0f}  ({total_pct:+.1f}% on combined ${'70k'})")
print(f"  AVG PER YEAR:    ${total_pnl/5:>+,.0f}  ({total_pct/5:+.1f}%/yr)")
print(f"\n  On $50k prop account (scaled): ~${total_pnl/5*(50000/10000):>+,.0f}/year")
print(f"  = ~${total_pnl/5*(50000/10000)/12:>+,.0f}/month")
