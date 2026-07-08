"""
S3 Challenge Simulation — Abnormal Volume at 4x size
Simulates prop firm challenge phase: 8% target, 5% daily limit, 10% max DD
Shows monthly return distribution and how often 8% target is hit
"""
import yfinance as yf
import pandas as pd

SYMBOLS         = ["QQQ", "GLD", "GDX", "SLV", "USO"]  # GDXJ excluded (failed)
START           = "2019-01-01"
END             = "2026-06-27"
VOL_THRESHOLD   = 1.5
PRICE_THRESHOLD = 0.01
HOLD_BARS       = 5
STOP_LOSS_PCT   = 0.02
CAPITAL_INIT    = 10_000
DAILY_LIMIT     = 0.05
DD_LIMIT        = 0.10
MONTHLY_TARGET  = 0.08

# Risk levels to compare
SCENARIOS = {
    "1x (conservative)":  0.01,
    "2x":                 0.02,
    "3x":                 0.03,
    "4x (challenge)":     0.04,
}

print("Downloading data...")
raw = {}
for sym in SYMBOLS:
    d = yf.download(sym, start=START, end=END, interval="1d", progress=False, auto_adjust=True)
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    raw[sym] = d

def compute_signals(d):
    c = d["Close"].squeeze()
    o = d["Open"].squeeze()
    v = d["Volume"].squeeze()
    vol_mean = v.rolling(66).mean().shift(1)
    vol_std  = v.rolling(66).std().shift(1)
    abnvol   = (v - vol_mean) / vol_std
    dayret   = (c - o) / o
    signal   = ((abnvol > VOL_THRESHOLD) & (dayret > PRICE_THRESHOLD)).astype(int)
    return pd.DataFrame({"close": c, "open": o, "signal": signal})

sig = {sym: compute_signals(raw[sym]) for sym in SYMBOLS}

def run_portfolio(risk_per_trade):
    N            = len(SYMBOLS)
    risk_scaled  = risk_per_trade / N
    capital      = CAPITAL_INIT
    open_pos     = {}
    trades, trade_dates = [], []
    monthly_caps = {}
    day_start    = capital
    cur_day      = None
    locked       = False
    month_start_cap = capital
    cur_month    = None

    all_dates = sorted(set().union(*[set(sig[s].index) for s in SYMBOLS]))

    for dt in all_dates[1:]:
        d = dt.date()
        m = (dt.year, dt.month)

        if d != cur_day:
            cur_day   = d
            day_start = capital
            locked    = False

        if m != cur_month:
            cur_month       = m
            month_start_cap = capital

        # Prop firm kill switches
        day_loss   = (capital - day_start)  / max(day_start, 1)
        total_loss = (capital - CAPITAL_INIT) / CAPITAL_INIT
        month_gain = (capital - month_start_cap) / max(month_start_cap, 1)

        if day_loss <= -DAILY_LIMIT or total_loss <= -DD_LIMIT:
            locked = True
        if month_gain >= MONTHLY_TARGET:
            # Target hit — record and pause rest of month
            monthly_caps[m] = capital
            # skip rest of month
            cur_month = None  # will re-enter next month reset
            locked = True

        if locked:
            monthly_caps[m] = capital
            continue

        for sym in SYMBOLS:
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
                    trade_dates.append(dt)
                    del open_pos[sym]
            elif signal == 1 and sym not in open_pos:
                shares = (capital * risk_scaled) / (o * STOP_LOSS_PCT)
                open_pos[sym] = dict(entry_p=o, stop_p=o*(1-STOP_LOSS_PCT),
                                     shares=shares, bars_held=0)

        monthly_caps[m] = capital

    # Build monthly returns series
    months  = sorted(monthly_caps.keys())
    mo_caps = [monthly_caps[m] for m in months]
    mo_rets = []
    prev = CAPITAL_INIT
    for cap in mo_caps:
        mo_rets.append((cap - prev) / prev)
        prev = cap

    t  = pd.Series(trades)
    eq = pd.Series([CAPITAL_INIT] + list(t.cumsum() + CAPITAL_INIT))
    dd = ((eq - eq.cummax()) / eq.cummax()).min()

    return {
        "capital":   capital,
        "ret":       (capital - CAPITAL_INIT) / CAPITAL_INIT,
        "max_dd":    dd,
        "trades":    len(t),
        "wr":        (t > 0).mean() if len(t) else 0,
        "pf":        t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else float("inf"),
        "mo_rets":   mo_rets,
        "months":    months,
        "mo_caps":   mo_caps,
    }

# ── RUN ALL SCENARIOS ──
print("\nRunning scenarios...\n")
results = {}
for label, risk in SCENARIOS.items():
    r = run_portfolio(risk)
    results[label] = r

# ── SUMMARY TABLE ──
print(f"{'='*72}")
print(f"S3 VOLUME MOMENTUM — SCENARIO COMPARISON (7 years, $10k)")
print(f"{'='*72}")
print(f"{'Scenario':<25} {'Return':>8} {'MaxDD':>7} {'Trades':>7} {'WR':>5} "
      f"{'PF':>5} {'8%+mo':>6} {'Avg/mo':>8}")
print("-"*72)

for label, r in results.items():
    mo = r["mo_rets"]
    hit8    = sum(1 for x in mo if x >= 0.08)
    avg_mo  = sum(mo) / len(mo) if mo else 0
    print(f"{label:<25} {r['ret']:>+7.1%} {r['max_dd']:>7.1%} {r['trades']:>7} "
          f"{r['wr']:>4.0%} {r['pf']:>5.2f} {hit8:>5}mo {avg_mo:>+7.2%}")

# ── MONTHLY DETAIL FOR 4x ──
r4 = results["4x (challenge)"]
mo_series = pd.Series(r4["mo_rets"], index=[f"{y}-{m:02d}" for y,m in r4["months"]])

print(f"\n{'='*72}")
print("MONTHLY RETURNS — 4x size")
print(f"{'='*72}")
hit  = [x for x in r4["mo_rets"] if x >= 0.08]
loss = [x for x in r4["mo_rets"] if x < 0]
flat = [x for x in r4["mo_rets"] if 0 <= x < 0.08]

print(f"  Months hitting 8% target: {len(hit)}/{len(r4['mo_rets'])} "
      f"({len(hit)/len(r4['mo_rets']):.0%})")
print(f"  Profitable months:        {len(flat)+len(hit)}/{len(r4['mo_rets'])} "
      f"({(len(flat)+len(hit))/len(r4['mo_rets']):.0%})")
print(f"  Loss months:              {len(loss)}/{len(r4['mo_rets'])} "
      f"({len(loss)/len(r4['mo_rets']):.0%})")
print(f"  Avg monthly return:       {sum(r4['mo_rets'])/len(r4['mo_rets']):+.2%}")
print(f"  Best month:               {max(r4['mo_rets']):+.1%}")
print(f"  Worst month:              {min(r4['mo_rets']):+.1%}")

print(f"\n  Year-by-year at 4x:")
print(f"  {'Year':<6} {'Return':>8} {'8%+ months':>12}")
yr_group = {}
for (y,m), ret in zip(r4["months"], r4["mo_rets"]):
    yr_group.setdefault(y, []).append(ret)
for yr, rets in sorted(yr_group.items()):
    hit_yr = sum(1 for x in rets if x >= 0.08)
    print(f"  {yr:<6} {sum(rets):>+7.1%}  {hit_yr} months hit 8%+")

# ── INCOME PROJECTION AT 4x ──
avg_mo = sum(r4["mo_rets"]) / len(r4["mo_rets"])
print(f"\n{'='*72}")
print("INCOME PROJECTION — S3 at 4x (challenge phase → funded)")
print(f"{'='*72}")
for acct, label in [(10_000,"$10k challenge"), (50_000,"$50k funded"),
                    (100_000,"$100k funded"),  (200_000,"$200k funded")]:
    mo  = acct * avg_mo * 0.8   # 80% after 20% prop firm cut
    yr  = mo * 12
    print(f"  {label:<20}: ${mo:>8,.0f}/mo  |  ${yr:>10,.0f}/yr")

print(f"\n  Challenge pass probability estimate:")
print(f"  Months hitting 8%+: {len(hit)}/{len(r4['mo_rets'])} = "
      f"{len(hit)/len(r4['mo_rets']):.0%} of months")
print(f"  With 2-attempt window: ~{min(1-(1-len(hit)/len(r4['mo_rets']))**2, 0.99):.0%} "
      f"chance of passing within 2 months")
