"""
sweep_v3_15min.py — 15-minute bars for 4x more signals
Same logic as sweep_v2 but on 15-min data:
  - Long-only (longs proven, shorts 0% WR in bull years)
  - Asian session low sweep + Previous-day low sweep
  - Bull regime: price > daily EMA50 AND daily EMA50 > daily EMA200
  - ATR + daily range filters
  - QQQ + SPY combined, shared capital pool
  - 0.8% risk per trade, 0.4% when parallel position open
"""
import pandas as pd
import matplotlib.pyplot as plt
import pytz

STOP_PCT   = 0.015
TARGET_RR  = 3.0
RISK_PCT   = 0.008
DAILY_CAP  = 0.05
TOTAL_CAP  = 0.10

FILES = {
    "QQQ": "/Users/colindayer/nas100_backtest/qqq_15min_7y.csv",
    "SPY": "/Users/colindayer/nas100_backtest/spy_15min_7y.csv",
}
eastern = pytz.timezone("US/Eastern")


def load_and_signal(sym, path):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    df = df[df["symbol"] == sym]
    df.index = df.index.tz_convert(eastern)
    data = df[["open","high","low","close"]].copy()
    data.columns = ["Open","High","Low","Close"]
    close, high, low = data["Close"], data["High"], data["Low"]

    # ── Asian session H/L (6pm-2am ET, belongs to next trading day) ──────────────
    def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
    def session_date(idx):
        return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()
    data["Asian"]       = data.index.map(is_asian)
    data["SessionDate"] = data.index.map(session_date)
    ab = data[data["Asian"]]
    data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
    data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())

    # ── Previous-day H/L ──────────────────────────────────────────────────────────
    data["Date"]    = data.index.date
    day_high = data.groupby("Date")["High"].max()
    day_low  = data.groupby("Date")["Low"].min()
    dates    = pd.Series(data.index.date, index=data.index)
    data["PrevDayHigh"] = dates.map(day_high.shift(1, fill_value=float("nan")).to_dict())
    data["PrevDayLow"]  = dates.map(day_low.shift(1,  fill_value=float("nan")).to_dict())

    # ── Session gate: London 2-5am ET, NY open 9:30am-12pm ET ────────────────────
    def in_session(x):
        h, m = x.hour, x.minute
        return (2 <= h < 5) or (h == 9 and m >= 30) or (10 <= h < 12)
    data["InSession"] = data.index.map(in_session)

    # ── ATR volatility filter (14-bar ATR vs 200-bar avg, on 15min bars) ──────────
    prev_close = close.shift(1)
    tr = pd.concat([high-low,(high-prev_close).abs(),(low-prev_close).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    data["HighVol"] = atr > 1.5 * atr.rolling(800).mean()   # 800 × 15min ≈ 200 hours

    # ── Daily range filter ────────────────────────────────────────────────────────
    data["DailyRange"]    = (data.groupby("Date")["High"].transform("max")
                            - data.groupby("Date")["Low"].transform("min"))
    data["AvgDailyRange"] = data["Date"].map(
        data.groupby("Date")["DailyRange"].first().rolling(14).mean()
    )
    data["RangeOk"] = (
        (data["DailyRange"] >= data["AvgDailyRange"] * 0.6) &
        (data["DailyRange"] <= data["AvgDailyRange"] * 1.4)
    )

    # ── Bull regime: daily EMA50 AND EMA200 ──────────────────────────────────────
    daily_close = data[data.index.hour == 16][["Close"]].copy()
    # use last 15-min bar of the 4pm hour as daily close proxy
    daily_close = daily_close[~daily_close.index.normalize().duplicated(keep="last")]
    daily_close.index = daily_close.index.date
    daily_ema50  = daily_close["Close"].ewm(span=50).mean()
    daily_ema200 = daily_close["Close"].ewm(span=200).mean()
    data["DailyEMA50"]   = data["Date"].map(daily_ema50.to_dict())
    data["DailyEMA200"]  = data["Date"].map(daily_ema200.to_dict())
    data["DailyUptrend"] = (
        (close > data["DailyEMA50"]) &
        (data["DailyEMA50"] > data["DailyEMA200"])
    )

    # ── Base condition ────────────────────────────────────────────────────────────
    base = data["InSession"] & data["DailyUptrend"] & ~data["HighVol"] & data["RangeOk"]

    # ── Sweep signals ─────────────────────────────────────────────────────────────
    asian_sweep = (low < data["AsianLow"]) & (close > data["AsianLow"]) & data["AsianLow"].notna()
    pd_sweep    = (low < data["PrevDayLow"]) & (close > data["PrevDayLow"]) & data["PrevDayLow"].notna()

    data["Signal"] = 0
    data.loc[base & pd_sweep,    "Signal"] = 1
    data.loc[base & asian_sweep, "Signal"] = 1

    return data


def combined_backtest(datasets):
    capital = 10000
    initial = capital
    trades_all = []
    all_idx = sorted(set().union(*[d.index for d in datasets.values()]))
    state = {sym: {"in_trade": False, "entry": 0, "stop": 0,
                   "target": 0, "shares": 0}
             for sym in datasets}
    day_start = capital; current_day = None; locked = False

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
                st.update({
                    "in_trade": True,
                    "entry":    price,
                    "stop":     price * (1 - STOP_PCT),
                    "target":   price * (1 + STOP_PCT * TARGET_RR),
                    "shares":   (capital * risk_pct) / (price * STOP_PCT),
                })
            elif st["in_trade"]:
                if price <= st["stop"] or price >= st["target"]:
                    pnl = st["shares"] * (price - st["entry"])
                    capital += pnl
                    trades_all.append({
                        "sym": sym, "year": ts.year, "month": ts.month,
                        "pnl": pnl, "win": pnl > 0,
                    })
                    st["in_trade"] = False

    return pd.DataFrame(trades_all), capital, initial


# ── MAIN ─────────────────────────────────────────────────────────────────────
print("Loading 15-min data and computing signals...")
datasets = {}
for sym, path in FILES.items():
    datasets[sym] = load_and_signal(sym, path)
    sig = (datasets[sym]["Signal"] == 1).sum()
    print(f"  {sym}: {sig} long signals")

print("\nRunning combined backtest...")
tdf, final_capital, initial_capital = combined_backtest(datasets)

if len(tdf) == 0:
    print("No trades — check signal logic")
else:
    wins   = tdf["win"].sum()
    losses = (~tdf["win"]).sum()
    trades = tdf["pnl"]

    equity = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
    peak   = equity.cummax()
    max_dd = ((equity - peak) / peak).min()
    pf     = trades[trades>0].sum() / abs(trades[trades<0].sum()) if losses > 0 else float("inf")

    print(f"\nFinal capital:  ${final_capital:,.0f}")
    print(f"Total return:   {(final_capital - initial_capital) / initial_capital:.1%}")
    print(f"Max drawdown:   {max_dd:.1%}")
    print(f"Total trades:   {len(tdf)}")
    print(f"Win rate:       {wins / len(tdf):.1%}")
    print(f"Avg win:        ${trades[trades > 0].mean():,.0f}")
    print(f"Avg loss:       ${trades[trades < 0].mean():,.0f}")
    print(f"Profit factor:  {pf:.2f}")
    print(f"Trades/month:   {len(tdf) / (7.5 * 12):.1f}")

    prop_ok = max_dd > -TOTAL_CAP
    print(f"\n{'✅' if prop_ok else '⚠️ '} Max drawdown {'passes' if prop_ok else 'BREACHES'} "
          f"{TOTAL_CAP:.0%} prop firm limit")

    print("\nYear  Trades  Win%    Return")
    for yr in sorted(tdf["year"].unique()):
        y = tdf[tdf["year"] == yr]
        print(f"{yr}  {len(y):>6}  {y['win'].mean():.0%}   ${y['pnl'].sum():+,.0f}")

    print("\nPer-symbol:")
    for sym in FILES:
        s = tdf[tdf["sym"] == sym]
        print(f"  {sym}: {len(s)} trades  {s['win'].mean():.0%} WR  ${s['pnl'].sum():+,.0f}")

    plt.figure(figsize=(14, 5))
    plt.plot(equity.values, color="steelblue")
    plt.axhline(initial_capital, color="gray", linestyle="--", linewidth=0.8)
    plt.title("QQQ + SPY 15-Min — Long-Only Asian + PD-Low Sweep, Bull Regime Filter (7 Years)")
    plt.xlabel("Trade number")
    plt.ylabel("Capital ($)")
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    plt.savefig("/Users/colindayer/nas100_backtest/equity_v3_15min.png", dpi=150)
    plt.close()
    print("Chart saved to equity_v3_15min.png")
