"""
sweep_v2.py — Multi-symbol Asian + Previous-Day-Low sweep strategy
Improvements over v1:
  - Long-only (shorts were 0% WR across almost all years)
  - Adds previous-day-low sweep as second signal type
  - Trades QQQ + SPY + IWM simultaneously (shared capital, 1 trade per symbol at a time)
  - Fixed daily EMA50 trend filter (was using hourly EMA200 which let shorts through)
  - ATR + daily range filters unchanged
"""
import pandas as pd
import matplotlib.pyplot as plt
import pytz

STOP_PCT   = 0.015
TARGET_RR  = 3.0
RISK_PCT   = 0.008   # 0.8% risk — keeps max drawdown under 10% prop firm limit
DAILY_CAP  = 0.05
TOTAL_CAP  = 0.10

FILES = {
    "QQQ": "/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv",
    "SPY": "/Users/colindayer/nas100_backtest/spy_hourly_7y.csv",
}
# IWM excluded — 30% WR and high correlation to QQQ in drawdowns
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

    # ── Asian session H/L (6pm-2am ET, mapped to the trading day that follows) ──
    def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
    def session_date(idx):
        return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()

    data["Asian"]      = data.index.map(is_asian)
    data["SessionDate"] = data.index.map(session_date)
    ab = data[data["Asian"]]
    data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
    data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())

    # ── Previous-day H/L ─────────────────────────────────────────────────────────
    data["Date"] = data.index.date
    day_high = data.groupby("Date")["High"].max()
    day_low  = data.groupby("Date")["Low"].min()
    dates    = pd.Series(data.index.date, index=data.index)
    data["PrevDayHigh"] = dates.map(day_high.shift(1, fill_value=float("nan")).to_dict())
    data["PrevDayLow"]  = dates.map(day_low.shift(1,  fill_value=float("nan")).to_dict())

    # ── Session gate (London 2-5am ET, NY 9:30am-12pm ET) ───────────────────────
    def in_session(x):
        h, m = x.hour, x.minute
        return (2 <= h < 5) or (h == 9 and m >= 30) or (10 <= h < 12)
    data["InSession"] = data.index.map(in_session)

    # ── ATR volatility filter ─────────────────────────────────────────────────────
    prev_close = close.shift(1)
    tr = pd.concat([high-low,(high-prev_close).abs(),(low-prev_close).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    data["HighVol"] = atr > 1.5 * atr.rolling(200).mean()

    # ── Daily range filter ────────────────────────────────────────────────────────
    data["DailyRange"] = (data.groupby("Date")["High"].transform("max")
                        - data.groupby("Date")["Low"].transform("min"))
    data["AvgDailyRange"] = data["Date"].map(
        data.groupby("Date")["DailyRange"].first().rolling(14).mean()
    )
    data["RangeOk"] = (
        (data["DailyRange"] >= data["AvgDailyRange"] * 0.6) &
        (data["DailyRange"] <= data["AvgDailyRange"] * 1.4)
    )

    # ── Daily EMA50 + EMA200 trend filter (both must confirm uptrend) ────────────
    daily_close = data[data.index.hour == 16][["Close"]].copy()
    daily_close.index = daily_close.index.date
    daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
    daily_ema50  = daily_close["Close"].ewm(span=50).mean()
    daily_ema200 = daily_close["Close"].ewm(span=200).mean()
    data["DailyEMA50"]   = data["Date"].map(daily_ema50.to_dict())
    data["DailyEMA200"]  = data["Date"].map(daily_ema200.to_dict())
    # Both EMAs must agree: price above 50d EMA AND 50d EMA above 200d EMA (bull regime)
    data["DailyUptrend"] = (
        (close > data["DailyEMA50"]) &
        (data["DailyEMA50"] > data["DailyEMA200"])
    )

    # ── Previous-week H/L ────────────────────────────────────────────────────────
    data["Week"] = data.index.to_period("W")
    week_low  = data.groupby("Week")["Low"].min()
    week_high = data.groupby("Week")["High"].max()
    data["PrevWeekLow"]  = data["Week"].map(week_low.shift(1).to_dict())
    data["PrevWeekHigh"] = data["Week"].map(week_high.shift(1).to_dict())

    # ── Sweep signals ─────────────────────────────────────────────────────────────
    base_cond = (
        data["InSession"] &
        data["DailyUptrend"] &
        ~data["HighVol"] &
        data["RangeOk"]
    )
    # Signal 1: Asian session low sweep
    asian_sweep_long = (
        (low < data["AsianLow"]) & (close > data["AsianLow"]) &
        data["AsianLow"].notna() & base_cond
    )
    # Signal 2: Previous-day low sweep
    pd_sweep_long = (
        (low < data["PrevDayLow"]) & (close > data["PrevDayLow"]) &
        data["PrevDayLow"].notna() & base_cond
    )
    # Signal 3: Previous-week low sweep
    pw_sweep_long = (
        (low < data["PrevWeekLow"]) & (close > data["PrevWeekLow"]) &
        data["PrevWeekLow"].notna() & base_cond
    )
    data["Signal"] = 0
    data.loc[pw_sweep_long,    "Signal"] = 1
    data.loc[pd_sweep_long,    "Signal"] = 1
    data.loc[asian_sweep_long, "Signal"] = 1   # highest-conviction setup overwrites

    return data


def run_backtest(data, capital, day_start_capital_ref, current_day_ref, locked_ref):
    """
    Runs the backtest loop for one symbol against shared capital.
    Returns list of trade dicts.
    """
    close = data["Close"]
    trades = []
    in_trade = False
    direction = 0
    entry_price = stop_price = target_price = shares = 0

    for i in range(1, len(data)):
        pass  # placeholder — handled in combined loop below

    return trades


def combined_backtest(datasets):
    """Run all symbols through one shared capital pool."""
    capital = 10000
    initial = capital
    trades_all = []

    # Align all symbols to a common datetime index
    all_idx = sorted(set().union(*[d.index for d in datasets.values()]))

    # Per-symbol trade state
    state = {sym: {"in_trade": False, "dir": 0, "entry": 0,
                   "stop": 0, "target": 0, "shares": 0}
             for sym in datasets}

    # Shared daily state
    day_start = capital
    current_day = None
    locked = False

    for ts in all_idx:
        bar_date = ts.date()

        if bar_date != current_day:
            current_day = bar_date
            day_start = capital
            locked = False

        daily_loss = (capital - day_start) / day_start
        total_dd   = (capital - initial) / initial
        if daily_loss <= -DAILY_CAP or total_dd <= -TOTAL_CAP:
            locked = True

        if locked:
            continue

        for sym, data in datasets.items():
            if ts not in data.index:
                continue
            row = data.loc[ts]
            price  = float(row["Close"])
            signal = 0
            # Look back one bar for signal
            iloc   = data.index.get_loc(ts)
            if iloc > 0:
                signal = int(data["Signal"].iloc[iloc - 1])

            st = state[sym]
            if not st["in_trade"] and signal == 1:
                # Scale risk down if another position is already open
                open_count = sum(1 for s in state.values() if s["in_trade"])
                risk_pct   = RISK_PCT * 0.5 if open_count > 0 else RISK_PCT
                st["in_trade"] = True
                st["dir"]    = 1
                st["entry"]  = price
                risk_cash    = capital * risk_pct
                st["stop"]   = price * (1 - STOP_PCT)
                st["target"] = price * (1 + STOP_PCT * TARGET_RR)
                st["shares"] = risk_cash / (price * STOP_PCT)

            elif st["in_trade"]:
                hit_stop   = price <= st["stop"]
                hit_target = price >= st["target"]
                if hit_stop or hit_target:
                    pnl = st["shares"] * (price - st["entry"])
                    capital += pnl
                    trades_all.append({
                        "sym":  sym,
                        "year": ts.year,
                        "month": ts.month,
                        "pnl":  pnl,
                        "win":  pnl > 0,
                    })
                    st["in_trade"] = False

    return pd.DataFrame(trades_all), capital, initial


# ── MAIN ─────────────────────────────────────────────────────────────────────
print("Loading data and computing signals...")
datasets = {}
for sym, path in FILES.items():
    datasets[sym] = load_and_signal(sym, path)
    sig_count = (datasets[sym]["Signal"] == 1).sum()
    print(f"  {sym}: {sig_count} long signals")

print("\nRunning combined backtest...")
tdf, final_capital, initial_capital = combined_backtest(datasets)

wins   = tdf["win"].sum()
losses = (~tdf["win"]).sum()
trades = tdf["pnl"]

equity = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
peak   = equity.cummax()
max_dd = ((equity - peak) / peak).min()

pf = trades[trades > 0].sum() / abs(trades[trades < 0].sum()) if losses > 0 else float("inf")

print(f"\nFinal capital:  ${final_capital:,.0f}")
print(f"Total return:   {(final_capital - initial_capital) / initial_capital:.1%}")
print(f"Max drawdown:   {max_dd:.1%}")
print(f"Total trades:   {len(tdf)}")
print(f"Win rate:       {wins / len(tdf):.1%}")
print(f"Avg win:        ${trades[trades > 0].mean():,.0f}")
print(f"Avg loss:       ${trades[trades < 0].mean():,.0f}")
print(f"Profit factor:  {pf:.2f}")

print("\nYear  Trades  Win%    Return")
for yr in sorted(tdf["year"].unique()):
    y   = tdf[tdf["year"] == yr]
    wr  = y["win"].mean()
    ret = y["pnl"].sum()
    print(f"{yr}  {len(y):>6}  {wr:.0%}   ${ret:+,.0f}")

print("\nPer-symbol breakdown:")
for sym in FILES:
    s    = tdf[tdf["sym"] == sym]
    wr   = s["win"].mean() if len(s) else 0
    ret  = s["pnl"].sum()
    print(f"  {sym}: {len(s)} trades  {wr:.0%} WR  ${ret:+,.0f}")

# Chart
plt.figure(figsize=(14, 5))
plt.plot(equity.values, color="steelblue")
plt.axhline(initial_capital, color="gray", linestyle="--", linewidth=0.8)
plt.title("QQQ + SPY — Asian + PD + PW Low Sweeps, Long-Only, Bull Regime Filter (7 Years)")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True, alpha=0.4)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_v2.png", dpi=150)
plt.close()
print("\nChart saved to equity_v2.png")
