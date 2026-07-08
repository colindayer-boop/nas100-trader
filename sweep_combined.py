"""
Combined backtest — only symbols that proved edge independently.
Same fixed parameters as per-instrument test. No changes.
Tests two portfolios:
  A) All 5 qualified: QQQ + SPY + GLD + XLK + MSFT
  B) Core 4 (stronger): QQQ + SPY + GLD + MSFT  (drops XLK — borderline PF 1.28)
"""
import pandas as pd
import pytz
import matplotlib.pyplot as plt

STOP_PCT   = 0.015
TARGET_RR  = 3.0
RISK_PCT   = 0.008
DAILY_CAP  = 0.05
TOTAL_CAP  = 0.10
ATR_MULT   = 1.5
RANGE_LOW  = 0.6
RANGE_HIGH = 1.4

eastern = pytz.timezone("US/Eastern")

QUALIFIED = {
    "QQQ":  "qqq_hourly_7y.csv",
    "SPY":  "spy_hourly_7y.csv",
    "GLD":  "gld_hourly_7y.csv",
    "XLK":  "xlk_hourly_7y.csv",
    "MSFT": "msft_hourly_7y.csv",
}
CORE4 = {k: v for k, v in QUALIFIED.items() if k != "XLK"}


def load(sym, path):
    df = pd.read_csv(f"/Users/colindayer/nas100_backtest/{path}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    df = df[df["symbol"] == sym]
    df.index = df.index.tz_convert(eastern)
    data = df[["open","high","low","close"]].copy()
    data.columns = ["Open","High","Low","Close"]
    close, high, low = data["Close"], data["High"], data["Low"]

    def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
    def session_date(idx):
        return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()
    data["Asian"]       = data.index.map(is_asian)
    data["SessionDate"] = data.index.map(session_date)
    ab = data[data["Asian"]]
    data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
    data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())

    data["Date"]     = data.index.date
    day_low  = data.groupby("Date")["Low"].min()
    dates    = pd.Series(data.index.date, index=data.index)
    data["PrevDayLow"] = dates.map(day_low.shift(1, fill_value=float("nan")).to_dict())

    def in_session(x):
        h, m = x.hour, x.minute
        return (2 <= h < 5) or (h == 9 and m >= 30) or (10 <= h < 12)
    data["InSession"] = data.index.map(in_session)

    prev_close = close.shift(1)
    tr = pd.concat([high-low,(high-prev_close).abs(),(low-prev_close).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    data["HighVol"] = atr > ATR_MULT * atr.rolling(200).mean()

    data["DailyRange"]    = (data.groupby("Date")["High"].transform("max")
                            - data.groupby("Date")["Low"].transform("min"))
    data["AvgDailyRange"] = data["Date"].map(
        data.groupby("Date")["DailyRange"].first().rolling(14).mean()
    )
    data["RangeOk"] = (
        (data["DailyRange"] >= data["AvgDailyRange"] * RANGE_LOW) &
        (data["DailyRange"] <= data["AvgDailyRange"] * RANGE_HIGH)
    )

    daily_close = data[data.index.hour == 16][["Close"]].copy()
    daily_close.index = daily_close.index.date
    daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
    ema50  = daily_close["Close"].ewm(span=50).mean()
    ema200 = daily_close["Close"].ewm(span=200).mean()
    data["DailyEMA50"]  = data["Date"].map(ema50.to_dict())
    data["DailyEMA200"] = data["Date"].map(ema200.to_dict())
    data["Uptrend"]     = (close > data["DailyEMA50"]) & (data["DailyEMA50"] > data["DailyEMA200"])

    base = data["InSession"] & data["Uptrend"] & ~data["HighVol"] & data["RangeOk"]
    data["Signal"] = 0
    data.loc[base & (low < data["PrevDayLow"])  & (close > data["PrevDayLow"])  & data["PrevDayLow"].notna(),  "Signal"] = 1
    data.loc[base & (low < data["AsianLow"])    & (close > data["AsianLow"])    & data["AsianLow"].notna(),    "Signal"] = 1
    return data


def run(datasets, label):
    capital = 10000; initial = capital
    trades_all = []
    all_idx = sorted(set().union(*[d.index for d in datasets.values()]))
    state = {sym: {"in_trade": False, "entry": 0, "stop": 0, "target": 0, "shares": 0}
             for sym in datasets}
    day_start = capital; current_day = None; locked = False
    equity_curve = [capital]

    for ts in all_idx:
        bar_date = ts.date()
        if bar_date != current_day:
            current_day = bar_date; day_start = capital; locked = False
        if (capital - day_start)/day_start <= -DAILY_CAP or \
           (capital - initial)/initial    <= -TOTAL_CAP:
            locked = True
        if locked:
            continue

        for sym, data in datasets.items():
            if ts not in data.index:
                continue
            iloc  = data.index.get_loc(ts)
            price = float(data["Close"].iloc[iloc])
            sig   = int(data["Signal"].iloc[iloc - 1]) if iloc > 0 else 0
            st    = state[sym]

            if not st["in_trade"] and sig == 1:
                open_count = sum(1 for s in state.values() if s["in_trade"])
                risk_pct   = RISK_PCT * 0.5 if open_count > 0 else RISK_PCT
                st["in_trade"] = True
                st["entry"]  = price
                st["stop"]   = price * (1 - STOP_PCT)
                st["target"] = price * (1 + STOP_PCT * TARGET_RR)
                st["shares"] = (capital * risk_pct) / (price * STOP_PCT)
            elif st["in_trade"]:
                if price <= st["stop"] or price >= st["target"]:
                    pnl = st["shares"] * (price - st["entry"])
                    capital += pnl
                    trades_all.append({"sym": sym, "year": ts.year, "pnl": pnl, "win": pnl > 0})
                    st["in_trade"] = False
                    equity_curve.append(capital)

    tdf = pd.DataFrame(trades_all)
    eq  = pd.Series(equity_curve)
    dd  = ((eq - eq.cummax()) / eq.cummax()).min()
    t   = tdf["pnl"]
    wr  = tdf["win"].mean()
    pf  = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else float("inf")
    ret = (capital - initial) / initial
    n_years = tdf["year"].nunique() if len(tdf) else 1
    annual  = (1 + ret) ** (1 / n_years) - 1

    print(f"\n{'='*55}")
    print(f"Portfolio: {label}")
    print(f"{'='*55}")
    print(f"Trades:       {len(tdf)}  (~{len(tdf)/7:.0f}/year, ~{len(tdf)/7/12:.1f}/month)")
    print(f"Win rate:     {wr:.1%}")
    print(f"Total return: {ret:.1%}  ({annual:.1%}/yr)")
    print(f"Max drawdown: {dd:.1%}  {'✅' if dd > -TOTAL_CAP else '⚠️ OVER 10%'}")
    print(f"Profit factor:{pf:.2f}")
    print(f"\nYear  Trades   WR    Return")
    for yr in sorted(tdf["year"].unique()):
        y = tdf[tdf["year"] == yr]
        print(f"{yr}  {len(y):>5}   {y['win'].mean():.0%}   ${y['pnl'].sum():+,.0f}")

    print(f"\nPer-symbol:")
    for sym in datasets:
        s = tdf[tdf["sym"] == sym]
        if len(s) == 0: continue
        print(f"  {sym}: {len(s):>3} trades  {s['win'].mean():.0%} WR  ${s['pnl'].sum():+,.0f}")

    return eq, label


# ── LOAD ALL ──────────────────────────────────────────────────────────
print("Loading data...")
all_data = {sym: load(sym, path) for sym, path in QUALIFIED.items()}
core4_data = {sym: all_data[sym] for sym in CORE4}

eq5, lab5 = run(all_data, "QQQ+SPY+GLD+XLK+MSFT (all 5 qualified)")
eq4, lab4 = run(core4_data, "QQQ+SPY+GLD+MSFT (core 4, excl. XLK)")

# Chart — both equity curves
fig, axes = plt.subplots(2, 1, figsize=(14, 8))
for ax, eq, lab in [(axes[0], eq5, lab5), (axes[1], eq4, lab4)]:
    ax.plot(eq.values, color="steelblue")
    ax.axhline(10000, color="gray", linestyle="--", linewidth=0.8)
    ax.fill_between(range(len(eq)), eq.values, 10000,
                    where=(eq.values >= 10000), alpha=0.15, color="green")
    ax.fill_between(range(len(eq)), eq.values, 10000,
                    where=(eq.values < 10000),  alpha=0.15, color="red")
    ax.set_title(lab)
    ax.set_ylabel("Capital ($)")
    ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_combined.png", dpi=150)
plt.close()
print("\nChart saved: equity_combined.png")
