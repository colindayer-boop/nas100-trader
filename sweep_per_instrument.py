"""
Per-instrument validation — same fixed parameters on every asset.
No parameter tuning. If the edge isn't there independently, we don't include it.
"""
import pandas as pd
import pytz

# ── FIXED PARAMS — never change these per-instrument ──────────────────
STOP_PCT   = 0.015
TARGET_RR  = 3.0
RISK_PCT   = 0.008
DAILY_CAP  = 0.05
TOTAL_CAP  = 0.10
ATR_MULT   = 1.5
RANGE_LOW  = 0.6
RANGE_HIGH = 1.4
# ──────────────────────────────────────────────────────────────────────

eastern = pytz.timezone("US/Eastern")

ALL_SYMBOLS = {
    "QQQ":  "qqq_hourly_7y.csv",
    "SPY":  "spy_hourly_7y.csv",
    "IWM":  "iwm_hourly_7y.csv",
    "GLD":  "gld_hourly_7y.csv",
    "XLK":  "xlk_hourly_7y.csv",
    "NVDA": "nvda_hourly_7y.csv",
    "AAPL": "aapl_hourly_7y.csv",
    "MSFT": "msft_hourly_7y.csv",
}


def run_single(sym, path):
    df = pd.read_csv(f"/Users/colindayer/nas100_backtest/{path}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    df = df[df["symbol"] == sym]
    df.index = df.index.tz_convert(eastern)
    data = df[["open","high","low","close"]].copy()
    data.columns = ["Open","High","Low","Close"]
    close, high, low = data["Close"], data["High"], data["Low"]

    # Asian session (6pm–2am ET → next trading day)
    def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
    def session_date(idx):
        return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()
    data["Asian"]       = data.index.map(is_asian)
    data["SessionDate"] = data.index.map(session_date)
    ab = data[data["Asian"]]
    data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
    data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())

    # Previous-day low
    data["Date"]       = data.index.date
    day_low  = data.groupby("Date")["Low"].min()
    dates    = pd.Series(data.index.date, index=data.index)
    data["PrevDayLow"] = dates.map(day_low.shift(1, fill_value=float("nan")).to_dict())

    # Session gate
    def in_session(x):
        h, m = x.hour, x.minute
        return (2 <= h < 5) or (h == 9 and m >= 30) or (10 <= h < 12)
    data["InSession"] = data.index.map(in_session)

    # ATR filter
    prev_close = close.shift(1)
    tr = pd.concat([high-low,(high-prev_close).abs(),(low-prev_close).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    data["HighVol"] = atr > ATR_MULT * atr.rolling(200).mean()

    # Daily range filter
    data["DailyRange"]    = (data.groupby("Date")["High"].transform("max")
                            - data.groupby("Date")["Low"].transform("min"))
    data["AvgDailyRange"] = data["Date"].map(
        data.groupby("Date")["DailyRange"].first().rolling(14).mean()
    )
    data["RangeOk"] = (
        (data["DailyRange"] >= data["AvgDailyRange"] * RANGE_LOW) &
        (data["DailyRange"] <= data["AvgDailyRange"] * RANGE_HIGH)
    )

    # Daily EMA50 + EMA200 bull regime
    daily_close = data[data.index.hour == 16][["Close"]].copy()
    daily_close.index = daily_close.index.date
    daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
    ema50  = daily_close["Close"].ewm(span=50).mean()
    ema200 = daily_close["Close"].ewm(span=200).mean()
    data["DailyEMA50"]   = data["Date"].map(ema50.to_dict())
    data["DailyEMA200"]  = data["Date"].map(ema200.to_dict())
    data["Uptrend"] = (close > data["DailyEMA50"]) & (data["DailyEMA50"] > data["DailyEMA200"])

    base = data["InSession"] & data["Uptrend"] & ~data["HighVol"] & data["RangeOk"]

    data["Signal"] = 0
    data.loc[base & (low < data["PrevDayLow"])  & (close > data["PrevDayLow"])  & data["PrevDayLow"].notna(),  "Signal"] = 1
    data.loc[base & (low < data["AsianLow"])    & (close > data["AsianLow"])    & data["AsianLow"].notna(),    "Signal"] = 1

    # Backtest
    capital = 10000; initial = capital
    trades_pnl = []; trade_years = []
    in_trade = False; entry = stop = target = shares = 0
    day_start = capital; current_day = None; locked = False

    for i in range(1, len(data)):
        bar_date = data.index[i].date()
        price    = float(close.iloc[i])
        signal   = int(data["Signal"].iloc[i - 1])

        if bar_date != current_day:
            current_day = bar_date; day_start = capital; locked = False
        if (capital - day_start)/day_start <= -DAILY_CAP or \
           (capital - initial)/initial    <= -TOTAL_CAP:
            locked = True
        if locked: continue

        if not in_trade and signal == 1:
            in_trade = True
            entry  = price
            stop   = price * (1 - STOP_PCT)
            target = price * (1 + STOP_PCT * TARGET_RR)
            shares = (capital * RISK_PCT) / (price * STOP_PCT)
        elif in_trade:
            if price <= stop or price >= target:
                pnl = shares * (price - entry)
                capital += pnl
                trades_pnl.append(pnl)
                trade_years.append(data.index[i].year)
                in_trade = False

    if not trades_pnl:
        return None

    t   = pd.Series(trades_pnl)
    eq  = pd.Series([initial] + list(t.cumsum() + initial))
    dd  = ((eq - eq.cummax()) / eq.cummax()).min()
    wr  = (t > 0).mean()
    pf  = t[t>0].sum() / abs(t[t<0].sum()) if (t<0).any() else float("inf")
    ret = (capital - initial) / initial

    yr_map = pd.Series(trade_years)
    by_year = {}
    for yr in sorted(set(trade_years)):
        mask = yr_map == yr
        yr_t = t[mask.values]
        by_year[yr] = {"wr": (yr_t > 0).mean(), "ret": yr_t.sum(), "n": len(yr_t)}

    return {
        "sym":      sym,
        "trades":   len(t),
        "wr":       wr,
        "ret":      ret,
        "max_dd":   dd,
        "pf":       pf,
        "by_year":  by_year,
        "pass_prop": dd > -TOTAL_CAP,
    }


# ── RUN ALL ────────────────────────────────────────────────────────────
print(f"Fixed params: stop={STOP_PCT:.1%}  RR={TARGET_RR}  risk={RISK_PCT:.1%}")
print(f"Filters: ATR×{ATR_MULT}  range {RANGE_LOW}×–{RANGE_HIGH}×  EMA50>EMA200\n")

results = []
for sym, path in ALL_SYMBOLS.items():
    r = run_single(sym, path)
    if r:
        results.append(r)
    else:
        print(f"{sym}: no trades")

# Summary table
print(f"{'Sym':<6} {'Trades':>6}  {'WR':>5}  {'Return':>8}  {'MaxDD':>7}  {'PF':>5}  {'PropFirm':>9}")
print("-" * 62)
passed, failed = [], []
for r in results:
    ok = "✅" if r["pass_prop"] else "⚠️ "
    print(f"{r['sym']:<6} {r['trades']:>6}  {r['wr']:>5.0%}  {r['ret']:>8.1%}  {r['max_dd']:>7.1%}  {r['pf']:>5.2f}  {ok}")
    (passed if r["pass_prop"] and r["ret"] > 0 else failed).append(r["sym"])

print(f"\n✅ Qualifies (profitable + DD < {TOTAL_CAP:.0%}): {passed}")
print(f"❌ Fails: {failed}")

# Year-by-year for qualifying symbols
print("\n── Year breakdown for qualifying symbols ──")
for r in results:
    if r["sym"] not in passed:
        continue
    print(f"\n{r['sym']}:")
    for yr, d in sorted(r["by_year"].items()):
        bar = "+" if d["ret"] >= 0 else "-"
        print(f"  {yr}  {d['n']:>2} trades  {d['wr']:.0%} WR  ${d['ret']:+,.0f}")
