"""
BTC Asian-Sweep validation — does the QQQ sweep edge transfer to Bitcoin?
SAME logic/params as QQQ (no BTC-specific tuning = honest transfer test), net of
REAL crypto costs (~8 bps round-trip, Bybit/Binance taker). Crypto sessions in UTC:
  Asian range 00:00-08:00 UTC ; sweep+reclaim window 08:00-16:00 UTC (London/NY).
Reports per-year + OOS split. Same discipline that killed IWM/DIA/TLT/EURUSD.
"""
import pandas as pd, numpy as np, time, os, warnings
import urllib.request, json
warnings.filterwarnings("ignore")
SLIP = 0.0004   # 4 bps/side = 8 bps round-trip (crypto taker; > ETF's 3 bps)
CACHE = "btc_1h.csv"

def fetch_binance():
    base = "https://api.binance.com/api/v3/klines"
    start = int(pd.Timestamp("2019-01-01").timestamp()*1000)
    end   = int(pd.Timestamp.utcnow().timestamp()*1000)
    rows = []
    while start < end:
        url = f"{base}?symbol=BTCUSDT&interval=1h&startTime={start}&limit=1000"
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data = json.loads(r.read())
        except Exception as e:
            print(f"  Binance fetch failed ({e}) — falling back to yfinance"); return None
        if not data: break
        rows += data
        start = data[-1][6] + 1
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=["ot","Open","High","Low","Close","Volume","ct",
                                     "qv","n","tb","tq","ig"])
    df["timestamp"] = pd.to_datetime(df["ot"], unit="ms", utc=True)
    df = df.set_index("timestamp")[["Open","High","Low","Close","Volume"]].astype(float)
    return df

if os.path.exists(CACHE):
    print("Loading cached BTC 1h...")
    d = pd.read_csv(CACHE, index_col=0, parse_dates=True)
else:
    print("Fetching BTCUSDT 1h from Binance (paginated)...")
    d = fetch_binance()
    if d is None:
        import yfinance as yf
        d = yf.download("BTC-USD", period="730d", interval="1h", progress=False)
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
        d = d[["Open","High","Low","Close","Volume"]]
        d.index = pd.to_datetime(d.index, utc=True)
    d.to_csv(CACHE)
print(f"  {len(d)} bars | {d.index.min()} → {d.index.max()}")

d["Date"] = d.index.date; d["H"] = d.index.hour
# Daily trend (own EMAs on 00:00 UTC daily close proxy = last bar of each day)
dc = d.groupby("Date")["Close"].last()
dc.index = pd.to_datetime(dc.index)
ema50 = dc.ewm(span=50).mean(); ema200 = dc.ewm(span=200).mean()
d["E50"]  = d["Date"].map(dict(zip(ema50.index.date, ema50)))
d["E200"] = d["Date"].map(dict(zip(ema200.index.date, ema200)))
pc = d["Close"].shift(1)
tr = pd.concat([d["High"]-d["Low"],(d["High"]-pc).abs(),(d["Low"]-pc).abs()],axis=1).max(axis=1)
atr = tr.rolling(14).mean(); d["HV"] = atr > 1.5*atr.rolling(200).mean()

# Asian range 00:00-08:00 UTC ; reclaim window 08:00-16:00 UTC
d["Asian"] = (d["H"] >= 0) & (d["H"] < 8)
ab = d[d["Asian"]]; d["AL"] = d["Date"].map(ab.groupby("Date")["Low"].min())
d["InS"] = (d["H"] >= 8) & (d["H"] < 16)
d["SL"] = (d["Low"] < d["AL"]) & (d["Close"] > d["AL"])
d["sig"] = (d["SL"] & d["InS"] & (d["Close"] > d["E50"]) & (d["E50"] > d["E200"]) &
            ~d["HV"] & d["AL"].notna()).astype(int)

def run(sl, rr=3.0, risk=0.006):
    yrs = {}
    for Y in sorted(set(d.index.year)):
        cap = init = 10_000; it=False; e=s=t=sh=0.; dt=None; ds=cap; cur=None; lock=False
        dd = d[d.index.year == Y]
        for i in range(1, len(dd)):
            day = dd["Date"].iloc[i]; price = float(dd["Close"].iloc[i]); g = int(dd["sig"].iloc[i-1])
            if day != cur: cur = day; ds = cap; lock = False
            if (cap-ds)/max(ds,1) <= -0.05 or (cap-init)/init <= -0.10: lock = True
            if lock: continue
            if it:
                if price <= s: cap += sh*(s-e)-sh*(e+s)*SLIP; it=False
                elif price >= t: cap += sh*(t-e)-sh*(e+t)*SLIP; it=False
            elif g and dt != day:
                it=True; dt=day; e=price; s=price*(1-sl); t=price*(1+sl*rr); sh=(cap*risk)/(price*sl)
        yrs[Y] = (cap-init)/init
    return yrs

yrs_all = sorted(set(d.index.year))
print("\n"+"="*70)
print("BTC ASIAN SWEEP — does the QQQ edge transfer? (net of ~8bps crypto costs)")
print("="*70)
print(f"{'Stop':<8}"+"".join(f"{y:>8}" for y in yrs_all)+f"{'avg':>8}{'signals':>9}")
print("-"*70)
print(f"  signals total: {int(d['sig'].sum())}")
for sl in [0.015, 0.025]:   # QQQ's 1.5% + a BTC-vol-scaled 2.5% (principled, not tuned-to-result)
    r = run(sl); avg = np.mean(list(r.values()))
    print(f"{sl:<8.1%}"+"".join(f"{r.get(y,0):>+8.1%}" for y in yrs_all)+f"{avg:>+8.1%}")
print("-"*70)
print("Read: consistently positive across years AND both stops = edge transfers.")
print("      mixed/negative = another instrument where the sweep doesn't transfer.")
