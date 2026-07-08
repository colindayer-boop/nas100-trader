import pandas as pd
import matplotlib.pyplot as plt
import pytz
import yfinance as yf

# ── LOAD QQQ INTRADAY DATA ──
df = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "QQQ"]

eastern = pytz.timezone("US/Eastern")
df.index = df.index.tz_convert(eastern)

data = df[["open", "high", "low", "close", "volume"]].copy()
data.columns = ["Open", "High", "Low", "Close", "Volume"]

close  = data["Close"]
high   = data["High"]
low    = data["Low"]
volume = data["Volume"]

data["Date"] = data.index.date

# ── DOWNLOAD VIX + SPY DAILY (for regime filters) ──
start_str = str(data.index.min().date())
end_str   = str(data.index.max().date() + pd.Timedelta(days=5))

print("Downloading ^VIX data...")
vix_raw = yf.download("^VIX", start=start_str, end=end_str, progress=False)
vix = vix_raw["Close"]
if isinstance(vix, pd.DataFrame):
    vix = vix.iloc[:, 0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma21 = vix.rolling(21).mean()

print("Downloading SPY data...")
spy_raw = yf.download("SPY", start=start_str, end=end_str, progress=False)
spy = spy_raw["Close"]
if isinstance(spy, pd.DataFrame):
    spy = spy.iloc[:, 0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
spy_ema50  = spy.ewm(span=50,  adjust=False).mean()
spy_ema200 = spy.ewm(span=200, adjust=False).mean()
spy_golden = (spy_ema50 > spy_ema200)  # True = golden cross (longs OK)

# Map daily values to intraday bars using .asof() (no lookahead)
all_dates_ts = pd.DatetimeIndex(
    [pd.Timestamp(d) for d in sorted(data["Date"].unique())]
)

vix_by_date  = vix_ma21.asof(all_dates_ts)      # Series indexed by Timestamp
spy_by_date  = spy_golden.asof(all_dates_ts)

vix_by_date.index  = [ts.date() for ts in vix_by_date.index]
spy_by_date.index  = [ts.date() for ts in spy_by_date.index]

def _vix_mult(v):
    if pd.isna(v):   return 1.0   # no data → trade normally
    if v > 25:       return 0.0   # stop all trades
    if v >= 20:      return 0.5   # half size
    return 1.0

vix_mult_map = vix_by_date.map(_vix_mult)
spy_bull_map = spy_by_date.fillna(True).astype(bool)

data["VIXMult"] = data["Date"].map(vix_mult_map).fillna(1.0)
data["SPYBull"]  = data["Date"].map(spy_bull_map).fillna(True)

# ── SESSION VWAP (reset daily at 9:30am) ──
data["RTH"]          = data.index.map(lambda x: 9 <= x.hour < 16)
data["TypicalPrice"] = (high + low + close) / 3

vwap_vals = []
cum_tpvol = cum_vol = 0.0
prev_date = None
for i in range(len(data)):
    row = data.iloc[i]
    d   = row["Date"]
    if d != prev_date:
        cum_tpvol = cum_vol = 0.0
        prev_date = d
    if row["RTH"] and row["Volume"] > 0:
        cum_tpvol += row["TypicalPrice"] * row["Volume"]
        cum_vol   += row["Volume"]
    vwap_vals.append(cum_tpvol / cum_vol if cum_vol > 0 else float("nan"))
data["VWAP"] = vwap_vals

# ── ASIAN SESSION HIGH/LOW ──
def is_asian(idx):    return idx.hour >= 18 or idx.hour < 2
def session_date(idx):
    if idx.hour >= 18: return (idx + pd.Timedelta(days=1)).date()
    return idx.date()

data["Asian"]       = data.index.map(is_asian)
data["SessionDate"] = data.index.map(session_date)
asian_bars = data[data["Asian"]]
data["AsianHigh"] = data["SessionDate"].map(asian_bars.groupby("SessionDate")["High"].max())
data["AsianLow"]  = data["SessionDate"].map(asian_bars.groupby("SessionDate")["Low"].min())

# ── SESSION FILTER (London + NY open) ──
data["InSession"] = data.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))

# ── VWAP REGIME: above VWAP = institutional bullish ──
data["BullRegime"] = close > data["VWAP"]

# ── ATR VOLATILITY FILTER ──
prev_close = close.shift(1)
tr  = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
atr = tr.rolling(14).mean()
data["HighVol"] = atr > 1.5 * atr.rolling(200).mean()

# ── DAILY EMA50 TREND (QQQ) ──
daily_close = data[data.index.hour == 16][["Close"]].copy()
daily_close.index = daily_close.index.date
daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
data["DailyEMA50"] = data["Date"].map(daily_close["Close"].ewm(span=50).mean().to_dict())
data["Uptrend"]    = close > data["DailyEMA50"]

# ── BASE SWEEP SIGNAL ──
data["SweepLow"] = (low < data["AsianLow"]) & (close > data["AsianLow"])
base_cond = (
    data["SweepLow"] & data["InSession"] & data["BullRegime"] &
    data["Uptrend"] & ~data["HighVol"] & data["AsianLow"].notna()
)

# Four signal variants
data["Sig_Base"] = base_cond.astype(int)
data["Sig_VIX"]  = (base_cond & (data["VIXMult"] > 0)).astype(int)   # VIX only
data["Sig_DC"]   = (base_cond & data["SPYBull"]).astype(int)          # death cross only
data["Sig_Both"] = (base_cond & (data["VIXMult"] > 0) & data["SPYBull"]).astype(int)

# ── BACKTEST ENGINE ──
def run_backtest(sig_col, use_vix_sizing=False, label=""):
    capital = 10_000; initial_capital = capital
    risk_pct = 0.01; sl_pct = 0.015; rr = 3.0
    daily_loss_limit = 0.05; max_dd_limit = 0.10

    trades, trade_years = [], []
    in_trade = 0
    entry_price = stop_price = target_price = shares = 0.0
    day_start_cap = capital; current_day = None
    trading_locked = breached = False

    for i in range(1, len(data)):
        bar_date  = data.index[i].date()
        price     = float(close.iloc[i])
        signal    = int(data[sig_col].iloc[i - 1])
        size_mult = float(data["VIXMult"].iloc[i - 1]) if use_vix_sizing else 1.0

        if bar_date != current_day:
            current_day   = bar_date
            day_start_cap = capital
            trading_locked = False

        if (capital - day_start_cap) / day_start_cap <= -daily_loss_limit or \
           (capital - initial_capital) / initial_capital <= -max_dd_limit:
            trading_locked = breached = True

        if trading_locked:
            continue

        if in_trade:
            if price <= stop_price:
                pnl = shares * (stop_price - entry_price)
                capital += pnl; trades.append(pnl); trade_years.append(data.index[i].year)
                in_trade = 0
            elif price >= target_price:
                pnl = shares * (target_price - entry_price)
                capital += pnl; trades.append(pnl); trade_years.append(data.index[i].year)
                in_trade = 0
        elif signal == 1 and size_mult > 0:
            in_trade     = 1
            entry_price  = price
            stop_price   = price * (1 - sl_pct)
            target_price = price * (1 + sl_pct * rr)
            shares       = (capital * risk_pct * size_mult) / (price * sl_pct)

    t  = pd.Series(trades)
    yr = pd.Series(trade_years)
    if len(t) == 0:
        return None
    equity = pd.Series([initial_capital] + list(t.cumsum() + initial_capital))
    max_dd = ((equity - equity.cummax()) / equity.cummax()).min()

    return dict(
        label    = label,
        capital  = capital,
        trades   = t,
        years    = yr,
        equity   = equity,
        max_dd   = max_dd,
        win_rate = (t > 0).mean(),
        ret      = (capital - initial_capital) / initial_capital,
        pf       = t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else float("inf"),
        breached = breached,
        initial  = initial_capital,
    )

# ── RUN ALL FOUR VARIANTS ──
results = {
    "Base": run_backtest("Sig_Base", use_vix_sizing=False, label="Base (existing filters)"),
    "VIX":  run_backtest("Sig_VIX",  use_vix_sizing=True,  label="+ VIX Regime Filter"),
    "DC":   run_backtest("Sig_DC",   use_vix_sizing=False,  label="+ Death Cross Filter"),
    "Both": run_backtest("Sig_Both", use_vix_sizing=True,   label="+ VIX + Death Cross"),
}

# ── SUMMARY TABLE ──
print(f"\n{'='*62}")
print("FILTER COMPARISON  (target: MaxDD < -10%, Return > +30%)")
print(f"{'='*62}")
for key, r in results.items():
    if r is None:
        print(f"\n[{key}] No trades generated."); continue
    dd_ok  = "✅" if r["max_dd"] > -0.10 else "❌"
    ret_ok = "✅" if r["ret"]    > 0.30  else "❌"
    passed = "✅ PASS" if (r["max_dd"] > -0.10 and r["ret"] > 0.30) else "❌ FAIL"
    print(f"\n{r['label']:35s}  [{passed}]")
    print(f"  Return: {r['ret']:+.1%} {ret_ok}  |  Max DD: {r['max_dd']:.1%} {dd_ok}  |  "
          f"Trades: {len(r['trades'])}  |  WR: {r['win_rate']:.0%}  |  PF: {r['pf']:.2f}")
    print(f"  Final: ${r['capital']:,.0f}  |  "
          f"{'⚠️  Prop firm breached' if r['breached'] else '✅ Prop firm OK'}")

# ── YEAR-BY-YEAR COMPARISON ──
all_years = sorted(
    set().union(*[set(r["years"].unique()) for r in results.values() if r is not None])
)
keys = [k for k in ["Base", "VIX", "DC", "Both"] if results[k] is not None]

print(f"\n{'='*62}")
print("YEAR-BY-YEAR P&L  ($ profit per year)")
print(f"{'='*62}")
print(f"{'Year':<6}", end="")
for k in keys:
    label_short = {"Base": "Base", "VIX": "+VIX", "DC": "+DC", "Both": "+Both"}[k]
    print(f"  {label_short:>10}", end="")
print()
print("-" * (6 + 12 * len(keys)))

for yr in all_years:
    print(f"{yr:<6}", end="")
    for k in keys:
        r    = results[k]
        mask = r["years"] == yr
        pnl  = r["trades"][mask.values].sum() if mask.any() else 0.0
        print(f"  {pnl:>+10,.0f}", end="")
    print()

# ── VIX REGIME INFO ──
print(f"\n{'='*62}")
print("VIX REGIME BREAKDOWN  (trading days)")
print(f"{'='*62}")
dates_series = pd.Series(data["Date"].unique())
vm = pd.Series(data.drop_duplicates("Date").set_index("Date")["VIXMult"])
n_stop   = (vm == 0.0).sum()
n_reduce = (vm == 0.5).sum()
n_normal = (vm == 1.0).sum()
total    = len(vm)
print(f"  VIX 21d avg > 25  (STOP):    {n_stop:>4} days ({n_stop/total:.0%})")
print(f"  VIX 21d avg 20-25 (REDUCE):  {n_reduce:>4} days ({n_reduce/total:.0%})")
print(f"  VIX 21d avg < 20  (NORMAL):  {n_normal:>4} days ({n_normal/total:.0%})")

# SPY death cross days
sb = pd.Series(data.drop_duplicates("Date").set_index("Date")["SPYBull"])
n_dc     = (~sb).sum()
n_gc     = sb.sum()
print(f"\n  SPY death cross (no longs):  {n_dc:>4} days ({n_dc/total:.0%})")
print(f"  SPY golden cross (OK):        {n_gc:>4} days ({n_gc/total:.0%})")

# ── EQUITY CURVES CHART ──
fig, axes = plt.subplots(2, 2, figsize=(14, 8))
axes = axes.flatten()
colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756"]

for ax, key, color in zip(axes, ["Base", "VIX", "DC", "Both"], colors):
    r = results[key]
    if r is None:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center", transform=ax.transAxes)
        continue
    ax.plot(r["equity"].values, color=color, linewidth=1.2)
    dd_mark = "✅" if r["max_dd"] > -0.10 else "❌"
    rt_mark = "✅" if r["ret"]    > 0.30  else "❌"
    ax.set_title(
        f"{r['label']}\n"
        f"Ret {r['ret']:+.1%} {rt_mark}  |  DD {r['max_dd']:.1%} {dd_mark}  |  {len(r['trades'])} trades",
        fontsize=9
    )
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Capital ($)")
    ax.grid(True, alpha=0.3)
    ax.axhline(r["initial"] * 0.90, color="red", linestyle="--", alpha=0.4, linewidth=0.8)

plt.suptitle("NAS100 Sweep: VIX Regime + Death Cross Filters", fontsize=12, fontweight="bold")
plt.tight_layout()
out_path = "/Users/colindayer/nas100_backtest/equity_filter_comparison.png"
plt.savefig(out_path, dpi=150)
plt.close()
print(f"\nChart saved: {out_path}")
