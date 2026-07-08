import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# Abnormal Volume Continuation — multi-symbol expansion
# Based on: Lee et al. (SSRN 2812010) and Taylor & Francis 2024
# Signal: volume > 1.5 std devs above 66-day baseline AND price move > 1%
# Hold: 5 days (effect persists 5 weeks per paper; 5 days captures early momentum)
# Applied to: QQQ, GLD, GDX, GDXJ, SLV, USO
# Less-efficient commodity/miner ETFs produce more frequent + cleaner signals than QQQ alone

SYMBOLS         = ["QQQ", "GLD", "GDX", "GDXJ", "SLV", "USO"]
START           = "2019-01-01"
END             = "2026-06-27"
VOL_THRESHOLD   = 1.5     # std devs above 66-day baseline
PRICE_THRESHOLD = 0.01    # 1% intraday price move
HOLD_BARS       = 5       # paper: effect persists 5 weeks; 5 days captures momentum burst
STOP_LOSS_PCT   = 0.02    # 2% stop — daily bars need room
RISK_PER_TRADE  = 0.01    # 1% of capital per trade
CAPITAL_INIT    = 10_000

# ── DOWNLOAD DAILY DATA ──
print("Downloading daily data for all symbols...")
raw = {}
for sym in SYMBOLS:
    d = yf.download(sym, start=START, end=END, interval="1d", progress=False, auto_adjust=True)
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    # Handle yfinance multi-level columns
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    raw[sym] = d
    print(f"  {sym}: {len(d)} bars")

# ── COMPUTE SIGNALS PER SYMBOL ──
def compute_signals(d):
    c = d["Close"].squeeze()
    o = d["Open"].squeeze()
    v = d["Volume"].squeeze()
    vol_mean  = v.rolling(66).mean().shift(1)
    vol_std   = v.rolling(66).std().shift(1)
    abnvol    = (v - vol_mean) / vol_std
    dayret    = (c - o) / o
    signal    = ((abnvol > VOL_THRESHOLD) & (dayret > PRICE_THRESHOLD)).astype(int)
    return pd.DataFrame({"close": c, "open": o, "abnvol": abnvol,
                         "dayret": dayret, "signal": signal})

sig = {sym: compute_signals(raw[sym]) for sym in SYMBOLS}

# ── INDIVIDUAL BACKTEST ENGINE ──
def backtest_single(sym_data, capital_init=CAPITAL_INIT):
    capital = capital_init
    trades, trade_years = [], []
    in_trade  = False; bars_held = 0
    entry_p   = stop_p = shares = 0.0
    day_start = capital; cur_day = None
    locked    = breached = False

    for i in range(1, len(sym_data)):
        idx    = sym_data.index[i]
        price  = float(sym_data["close"].iloc[i])
        o      = float(sym_data["open"].iloc[i])
        signal = int(sym_data["signal"].iloc[i - 1])

        if pd.isna(price) or pd.isna(o):
            continue

        if idx.date() != cur_day:
            cur_day   = idx.date()
            day_start = capital
            locked    = False

        if (capital - day_start) / day_start <= -0.05 or \
           (capital - capital_init) / capital_init <= -0.10:
            locked = breached = True

        if locked:
            continue

        if in_trade:
            bars_held += 1
            hit_stop  = price <= stop_p
            hit_time  = bars_held >= HOLD_BARS
            if hit_stop or hit_time:
                exit_p = stop_p if hit_stop else price
                pnl    = shares * (exit_p - entry_p)
                capital += pnl
                trades.append(pnl)
                trade_years.append(idx.year)
                in_trade = False; bars_held = 0
        elif signal == 1:
            in_trade = True
            entry_p  = o
            stop_p   = o * (1 - STOP_LOSS_PCT)
            shares   = (capital * RISK_PER_TRADE) / (o * STOP_LOSS_PCT)
            bars_held = 0

    t  = pd.Series(trades, dtype=float)
    yr = pd.Series(trade_years)
    if len(t) == 0:
        return None
    eq = pd.Series([capital_init] + list(t.cumsum() + capital_init))
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    return dict(capital=capital, trades=t, years=yr, equity=eq, max_dd=dd,
                win_rate=(t > 0).mean(), ret=(capital - capital_init) / capital_init,
                pf=t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else float("inf"),
                breached=breached, n_signals=(sym_data["signal"] == 1).sum())

# ── RUN INDIVIDUAL BACKTESTS ──
print("\nRunning individual backtests...")
ind = {sym: backtest_single(sig[sym]) for sym in SYMBOLS}

# ── COMBINED PORTFOLIO BACKTEST ──
# Equal-weight allocation: risk per trade = RISK_PER_TRADE / N_symbols
# This caps maximum simultaneous portfolio risk at 1% even if all symbols are in a trade,
# preventing correlated crashes (e.g. 2020) from breaching the prop firm DD limit.
# Only includes symbols that pass individual minimum criteria (PF > 1.0, DD > -10%).
def backtest_portfolio(portfolio_syms):
    N      = len(portfolio_syms)
    if N == 0:
        return None
    capital      = CAPITAL_INIT
    capital_init = CAPITAL_INIT
    open_pos     = {}
    trades, trade_years = [], []
    equity_by_day = {}
    day_start = capital; cur_day = None
    locked = breached = False

    all_dates = sorted(set().union(*[set(sig[s].index) for s in portfolio_syms]))

    for dt in all_dates[1:]:
        d = dt.date()
        if d != cur_day:
            cur_day   = d
            day_start = capital
            locked    = False

        if (capital - day_start) / day_start <= -0.05 or \
           (capital - capital_init) / capital_init <= -0.10:
            locked = breached = True

        if locked:
            equity_by_day[dt] = capital
            continue

        for sym in portfolio_syms:
            sd = sig[sym]
            if dt not in sd.index:
                continue
            pos = sd.index.get_loc(dt)
            if pos == 0:
                continue
            price  = float(sd["close"].iloc[pos])
            o      = float(sd["open"].iloc[pos])
            signal = int(sd["signal"].iloc[pos - 1])
            if pd.isna(price) or pd.isna(o):
                continue

            if sym in open_pos:
                t = open_pos[sym]
                t["bars_held"] += 1
                hit_stop = price <= t["stop_p"]
                hit_time = t["bars_held"] >= HOLD_BARS
                if hit_stop or hit_time:
                    exit_p = t["stop_p"] if hit_stop else price
                    pnl    = t["shares"] * (exit_p - t["entry_p"])
                    capital += pnl
                    trades.append(pnl)
                    trade_years.append(dt.year)
                    del open_pos[sym]
            elif signal == 1:
                # Equal-weight: each slot risks 1/N of RISK_PER_TRADE
                risk_scaled = RISK_PER_TRADE / N
                shares = (capital * risk_scaled) / (o * STOP_LOSS_PCT)
                open_pos[sym] = dict(entry_p=o, stop_p=o * (1 - STOP_LOSS_PCT),
                                     shares=shares, bars_held=0)

        equity_by_day[dt] = capital

    t     = pd.Series(trades, dtype=float)
    yr    = pd.Series(trade_years)
    eq_ts = pd.Series(equity_by_day)
    eq    = pd.Series([capital_init] + list(t.cumsum() + capital_init))
    dd    = ((eq - eq.cummax()) / eq.cummax()).min()
    return dict(capital=capital, trades=t, years=yr, equity=eq, equity_ts=eq_ts,
                max_dd=dd, win_rate=(t > 0).mean() if len(t) else 0,
                ret=(capital - capital_init) / capital_init,
                pf=t[t > 0].sum() / abs(t[t < 0].sum()) if (t < 0).any() else float("inf"),
                breached=breached,
                n_signals=sum((sig[s]["signal"] == 1).sum() for s in portfolio_syms),
                symbols=portfolio_syms, N=N)

# Auto-select symbols that pass individual minimum quality bar
passing = [s for s in SYMBOLS
           if ind[s] is not None and ind[s]["pf"] > 1.0 and ind[s]["max_dd"] > -0.10]
failing = [s for s in SYMBOLS if s not in passing]
print(f"\nPortfolio symbols: {passing}")
if failing:
    print(f"Excluded (failed individual test): {failing}")

print("Running combined portfolio backtest...")
portfolio = backtest_portfolio(passing)

# ── PRINT INDIVIDUAL RESULTS TABLE ──
print(f"\n{'='*74}")
print("INDIVIDUAL SYMBOL RESULTS  (1% risk/trade, 2% stop, 5-day hold)")
print(f"{'='*74}")
print(f"{'Symbol':7} {'Sigs':>5} {'Trades':>7} {'WR':>6} {'PF':>6} {'Return':>9} {'MaxDD':>8}")
print("-" * 74)
for sym in SYMBOLS:
    r = ind[sym]
    if r is None:
        print(f"{sym:7} {'0':>5} {'0':>7} {'n/a':>6} {'n/a':>6} {'n/a':>9} {'n/a':>8}")
        continue
    dd_ok  = "ok" if r["max_dd"] > -0.10 else "!!"
    pf_ok  = "ok" if r["pf"]    >  1.30  else "--"
    print(f"{sym:7} {r['n_signals']:>5} {len(r['trades']):>7} "
          f"{r['win_rate']:>5.0%} {r['pf']:>6.2f} "
          f"{r['ret']:>+8.1%} {r['max_dd']:>7.1%}  DD:{dd_ok} PF:{pf_ok}")

# ── PRINT COMBINED RESULTS ──
p = portfolio
dd_ok  = "✅" if p["max_dd"] > -0.10 else "❌"
ret_ok = "✅" if p["ret"]    >  0.0  else "❌"
pf_ok  = "✅" if p["pf"]     >  1.30 else "❌"
n_years = 7
tpy     = len(p["trades"]) / n_years

print(f"\n{'='*74}")
print(f"COMBINED PORTFOLIO ({p['N']} symbols: {', '.join(p['symbols'])},")
print(f"  equal weight, max 1 trade/symbol, risk={RISK_PER_TRADE/p['N']:.2%}/trade)")
print(f"{'='*74}")
print(f"  Return:  {p['ret']:+.1%} {ret_ok}")
print(f"  Max DD:  {p['max_dd']:.1%} {dd_ok}")
print(f"  Trades:  {len(p['trades'])} total  ({tpy:.1f}/year)")
print(f"  Win%:    {p['win_rate']:.0%}  |  PF: {p['pf']:.2f} {pf_ok}")
print(f"  Final:   ${p['capital']:,.0f}")
print(f"  Status:  {'⚠️  Prop firm breached' if p['breached'] else '✅ Prop firm OK'}")
print(f"  Targets: trades/yr {'✅' if tpy >= 25 else '❌'} ({tpy:.1f}≥25)  "
      f"PF {'✅' if p['pf']>1.3 else '❌'}  MaxDD {'✅' if p['max_dd']>-0.10 else '❌'}")

# ── YEAR-BY-YEAR COMBINED ──
all_years = sorted(p["years"].unique()) if len(p["years"]) else []
print(f"\n{'='*74}")
print("YEAR-BY-YEAR  (combined portfolio)")
print(f"{'='*74}")
print(f"{'Year':<6}  {'Trades':>7}  {'Win%':>5}  {'P&L':>10}  {'Cum P&L':>10}")
print("-" * 48)
cum = 0.0
for yr in all_years:
    mask = p["years"] == yr
    yt   = p["trades"][mask.values]
    pnl  = yt.sum()
    cum += pnl
    print(f"{yr:<6}  {len(yt):>7}  {(yt>0).mean():>5.0%}  "
          f"{pnl:>+10,.0f}  {cum:>+10,.0f}")

# ── YEAR-BY-YEAR PER-SYMBOL (P&L columns) ──
print(f"\n{'='*74}")
print("YEAR-BY-YEAR P&L BY SYMBOL ($)")
print(f"{'='*74}")
sym_header = "".join(f"  {s:>7}" for s in SYMBOLS)
print(f"{'Year':<6}{sym_header}")
print("-" * (6 + 9 * len(SYMBOLS)))

all_yr_set = set()
for sym in SYMBOLS:
    if ind[sym]: all_yr_set.update(ind[sym]["years"].unique())
for yr in sorted(all_yr_set):
    row = f"{yr:<6}"
    for sym in SYMBOLS:
        r = ind[sym]
        if r is None:
            row += f"  {'n/a':>7}"; continue
        mask = r["years"] == yr
        pnl  = r["trades"][mask.values].sum() if mask.any() else 0.0
        row += f"  {pnl:>+7,.0f}"
    print(row)

# ── CHARTS ──
fig = plt.figure(figsize=(16, 11))
gs  = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.32)
colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#b279a2", "#ff9da6"]

for idx_s, sym in enumerate(SYMBOLS):
    row = idx_s // 3
    col = idx_s  % 3
    ax  = fig.add_subplot(gs[row, col])
    r   = ind[sym]
    if r is None:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(sym)
        continue
    ax.plot(r["equity"].values, color=colors[idx_s], linewidth=1.1)
    ax.axhline(CAPITAL_INIT * 0.90, color="red", linestyle="--", alpha=0.4, linewidth=0.8)
    dd_tag = "ok" if r["max_dd"] > -0.10 else "!!"
    ax.set_title(
        f"{sym}  Ret:{r['ret']:+.1%}  DD:{r['max_dd']:.1%}[{dd_tag}]  "
        f"T:{len(r['trades'])}  PF:{r['pf']:.2f}",
        fontsize=8
    )
    ax.set_xlabel("Trade #", fontsize=7)
    ax.set_ylabel("Capital ($)", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.3)

# Combined portfolio — bottom row, full width
ax_comb = fig.add_subplot(gs[2, :])
eq_ts = portfolio["equity_ts"]
ax_comb.plot(eq_ts.index, eq_ts.values, color="#333333", linewidth=1.4)
ax_comb.axhline(CAPITAL_INIT * 0.90, color="red", linestyle="--", alpha=0.5,
                linewidth=0.9, label="10% DD limit")
ax_comb.set_title(
    f"Combined Portfolio (6 symbols)  |  "
    f"Ret:{p['ret']:+.1%}  DD:{p['max_dd']:.1%}  "
    f"Trades:{len(p['trades'])} ({tpy:.1f}/yr)  PF:{p['pf']:.2f}",
    fontsize=9
)
ax_comb.set_xlabel("Date"); ax_comb.set_ylabel("Capital ($)")
ax_comb.legend(fontsize=8); ax_comb.grid(True, alpha=0.3)

fig.suptitle(
    "Abnormal Volume Continuation  (VOL>1.5sd + price>1%, 5-day hold)\n"
    "Lee et al. SSRN 2812010 / Taylor & Francis 2024",
    fontsize=11, fontweight="bold"
)
out = "/Users/colindayer/nas100_backtest/equity_abvol_multisym.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nChart saved: {out}")
