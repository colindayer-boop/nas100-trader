import pandas as pd, numpy as np, warnings, datetime
warnings.filterwarnings("ignore")

# ========== Load Nasdaq + Gold from full_yearly.py (pre-run-all section) ==========
full_yearly_code = open('/Users/colindayer/nas100_backtest/full_yearly.py').read()
# Execute everything before the line that starts with "# ── run all"
split_point = full_yearly_code.find('# ── run all')
exec(full_yearly_code[:split_point])  # This defines q, gld, vmult, SLIP, YEARS, and helper functions (asof, vmult, neg_gex, is_bull, sd, isA)

# Define trades_intraday and trades_gold as in combined_3pillar.py
def trades_intraday(sig, risk, sl, rr, short=False):
    cap=10_000; rows=[]; it=False; e=s=t=sh=0.; ds=cap; cur=None; lock=False; dt=None
    for i in range(1,len(q)):
        dd=q.index[i].date(); price=float(q["Close"].iloc[i]); g=int(q[sig].iloc[i-1]); vm=vmult(q.index[i-1].date())
        if dd!=cur: cur=dd; ds=cap; lock=False
        if (cap-ds)/max(ds,1)<=-0.05 or (cap-10_000)/10_000<=-0.10: lock=True
        if lock: continue
        if it:
            p=None
            if not short:
                if price<=s: p=sh*(s-e)-sh*(e+s)*SLIP
                elif price>=t: p=sh*(t-e)-sh*(e+t)*SLIP
            else:
                if price>=s: p=sh*(e-price)-sh*(e+s)*SLIP
                elif price<=t: p=sh*(e-price)-sh*(e+t)*SLIP
            if p is not None: cap+=p; rows.append((dd,p)); it=False
        elif g and vm>0 and dt!=dd:
            it=True; dt=dd; e=price
            if not short: s=price*(1-sl); t=price*(1+sl*rr)
            else: s=price*(1+sl); t=price*(1-sl*rr)
            sh=(cap*risk*vm)/(price*sl)
    return rows

def trades_gold(risk=0.005, sl=0.012, rr=2.0):
    cap=10_000; rows=[]; it=False; e=s=t=sh=0.
    for i in range(1,len(gld)):
        price=float(gld["Close"].iloc[i]); g=int(gld["FVG"].iloc[i-1]); dd=gld.index[i].date()
        if it:
            if price<=s: p=sh*(s-e)-sh*(e+s)*SLIP; cap+=p; rows.append((dd,p)); it=False
            elif price>=t: p=sh*(t-e)-sh*(e+t)*SLIP; cap+=p; rows.append((dd,p)); it=False
        elif g: it=True; e=price; s=price*(1-sl); t=price*(1+sl*rr); sh=(cap*risk)/(price*sl)
    return rows

# ========== Load BTC preamble ==========
btc_preamble = open('/Users/colindayer/nas100_backtest/btc_sweep_test.py').read()
# Execute everything before the line "def run(sl"
split_point2 = btc_preamble.find('def run(sl')
exec(btc_preamble[:split_point2])  # This defines d and SLIP (note: SLIP may be overwritten)

# Define trades_btc as in combined_3pillar.py
def trades_btc(sl=0.025, rr=3.0, risk=0.006):
    cap=10_000; rows=[]; it=False; e=s=t=sh=0.; dt=None; ds=cap; cur=None; lock=False
    for i in range(1,len(d)):
        dd=d["Date"].iloc[i]; price=float(d["Close"].iloc[i]); g=int(d["sig"].iloc[i-1])
        if dd!=cur: cur=dd; ds=cap; lock=False
        if (cap-ds)/max(ds,1)<=-0.05 or (cap-10_000)/10_000<=-0.10: lock=True
        if lock: continue
        if it:
            if price<=s: p=sh*(s-e)-sh*(e+s)*SLIP; cap+=p; rows.append((dd,p)); it=False
            elif price>=t: p=sh*(t-e)-sh*(e+t)*SLIP; cap+=p; rows.append((dd,p)); it=False
        elif g and dt!=dd:
            it=True; dt=dd; e=price; s=price*(1-sl); t=price*(1+sl*rr); sh=(cap*risk)/(price*sl)
    return rows

# Daily aggregation function
def daily(rows):
    s = pd.Series(0.0, index=[])
    by = {}
    for dd,p in rows: by[pd.Timestamp(dd)] = by.get(pd.Timestamp(dd),0)+p
    return pd.Series(by).sort_index()

# Compute pillar P&L
nasdaq = (trades_intraday("S1",0.007,0.015,3.0) + trades_intraday("S4",0.005,0.015,3.0) +
          trades_intraday("S5L",0.005,0.010,2.5) + trades_intraday("S5S",0.003,0.010,2.5,short=True))
gold = trades_gold()
btc = trades_btc()

nasdaq_d = daily(nasdaq)
gold_d = daily(gold)
btc_d = daily(btc)

# Align
nasdaq_d.index = pd.to_datetime(nasdaq_d.index)
gold_d.index = pd.to_datetime(gold_d.index)
btc_d.index = pd.to_datetime(btc_d.index)

df_raw = pd.concat([nasdaq_d, gold_d, btc_d], axis=1)
df_raw.columns = ['nasdaq','gold','btc']
df_raw = df_raw.fillna(0.0)

print("Data loaded. Shape:", df_raw.shape)
print("Date range:", df_raw.index.min(), "to", df_raw.index.max())

# ========== Allocation Engine ==========
ret_raw = df_raw / 10000.0  # daily returns if fully allocated
alldates = pd.date_range(start=df_raw.index.min(), end=df_raw.index.max(), freq='D')
ret = ret_raw.reindex(alldates).fillna(0.0)
pnl = df_raw.reindex(alldates).fillna(0.0)

lookback_vol = 63
lookback_sharpe = 252
cost_bps = 0.0005  # 5 bps

r = ret.values
T = len(r)
r_df = pd.DataFrame(r, index=ret.index, columns=['nasdaq','gold','btc'])

def simulate_scheme(weight_func):
    """
    weight_func(i, hist) -> weights for day i based on history up to i-1
    Returns array of length 3.
    """
    capital = 10_000.0
    equity = [capital]
    daily_net = []
    w_prev = np.array([1/3, 1/3, 1/3])

    for i in range(T):
        date = ret.index[i]
        rebalance = (ret.index.to_series().dt.is_month_start)[i]
        if rebalance and i > 0:
            # compute weights using data up to i-1
            hist = r_df.iloc[:i]
            w = weight_func(i, hist)
            # ensure weights sum to 1 (should already)
            w = w / w.sum() if w.sum() > 0 else np.array([1/3, 1/3, 1/3])
        else:
            w = w_prev

        turnover = np.sum(np.abs(w - w_prev)) if i > 0 else 0.0
        cost = cost_bps * turnover * equity[-1] if i > 0 else 0.0
        gross = np.dot(w, r[i]) * equity[-1]
        net = gross - cost
        new_equity = equity[-1] + net
        equity.append(new_equity)
        daily_net.append(net)
        w_prev = w

    equity = np.array(equity)
    return equity, daily_net

# Weight functions
def inv_vol_weights(i, hist):
    vol = hist.std()
    inv_vol = 1.0 / vol.replace(0, np.nan)
    inv_vol = inv_vol.fillna(0)
    if inv_vol.sum() == 0:
        return np.array([1/3, 1/3, 1/3])
    w = inv_vol.values
    return w / w.sum()

def risk_parity_weights(i, hist):
    cov = hist.cov()
    try:
        inv_cov = np.linalg.pinv(cov.values)
        ones = np.ones(3)
        w = inv_cov @ ones
        if np.any(w < 0):
            # fallback to inv vol
            vol = hist.std()
            inv_vol = 1.0 / vol.replace(0, np.nan)
            inv_vol = inv_vol.fillna(0)
            if inv_vol.sum() == 0:
                return np.array([1/3, 1/3, 1/3])
            w = inv_vol.values
            return w / w.sum()
        w = np.abs(w)
        if w.sum() == 0:
            return np.array([1/3, 1/3, 1/3])
        return w / w.sum()
    except:
        vol = hist.std()
        inv_vol = 1.0 / vol.replace(0, np.nan)
        inv_vol = inv_vol.fillna(0)
        if inv_vol.sum() == 0:
            return np.array([1/3, 1/3, 1/3])
        w = inv_vol.values
        return w / w.sum()

def sharpe_weights(i, hist):
    if i >= lookback_sharpe:
        recent = hist.iloc[-lookback_sharpe:]
    else:
        recent = hist
    mean_excess = recent.mean() * 252
    vol_ann = recent.std() * np.sqrt(252)
    sharpe = mean_excess / vol_ann
    sharpe = sharpe.fillna(0)
    sharpe_pos = np.maximum(sharpe.values, 0)
    if sharpe_pos.sum() == 0:
        return np.array([1/3, 1/3, 1/3])
    return sharpe_pos / sharpe_pos.sum()

def equal_weights(i, hist):
    return np.array([1/3, 1/3, 1/3])

# Run simulations
print("\nRunning simulations...")
schemes = {
    'EqualWeight': equal_weights,
    'InvVol': inv_vol_weights,
    'RiskParity': risk_parity_weights,
    'RollingSharpe': sharpe_weights
}

results = {}
for name, wfunc in schemes.items():
    equity, daily_net = simulate_scheme(wfunc)
    results[name] = {'equity': equity, 'daily_net': daily_net}

# Compute metrics
def compute_metrics(equity, daily_ret):
    total_return = (equity[-1] - equity[0]) / equity[0]
    days = len(equity) - 1
    years = days / 252.0  # approximate trading days
    cagr = (equity[-1] / equity[0])**(1/years) - 1 if years>0 else 0
    strat_ret = np.diff(equity) / equity[:-1]
    strat_ret = strat_ret[np.isfinite(strat_ret)]
    if len(strat_ret) == 0:
        sharpe_ratio = 0
    else:
        sharpe_ratio = np.mean(strat_ret) / np.std(strat_ret) * np.sqrt(252) if np.std(strat_ret) > 0 else 0
    roll_max = np.maximum.accumulate(equity)
    drawdown = (equity - roll_max) / roll_max
    max_dd = np.min(drawdown)
    return {
        'CAGR': cagr,
        'Sharpe': sharpe_ratio,
        'MaxDD': max_dd,
        'FinalEquity': equity[-1],
        'TotalReturn': total_return
    }

print("\n" + "="*60)
print("PORTFOLIO ALLOCATION RESULTS (Monthly Rebalancing, 5 bps turnover cost)")
print("="*60)
print(f"{'Scheme':<12} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8} {'Final':>10}")
print("-"*60)
for name in schemes:
    m = compute_metrics(results[name]['equity'], results[name]['daily_net'])
    print(f"{name:<12} {m['CAGR']:>7.2%} {m['Sharpe']:>7.2f} {m['MaxDD']:>7.2%} {m['FinalEquity']:>10.0f}")
print("-"*60)

# OOS validation: split at end of 2022
print("\n" + "="*60)
print("OUT-OF-SAMPLE VALIDATION (Train: 2019-2022, Test: 2023-2025)")
print("="*60)
# Find split index
split_date = pd.Timestamp('2022-12-31')
try:
    split_idx = ret.index.get_indexer([split_date], method='bfill')[0]
except:
    split_idx = int(0.8 * T)
print(f"Split index: {split_idx} (date: {ret.index[split_idx]})")

oos_results = {}
for name, wfunc in schemes.items():
    equity_full = results[name]['equity']
    oos_equity = equity_full[split_idx:]  # includes equity at split_idx
    if len(oos_equity) == 0:
        oos_results[name] = {'CAGR': 0, 'Sharpe': 0, 'MaxDD': 0, 'Final': 0}
        continue
    # Compute metrics on OOS segment
    oos_ret = np.diff(oos_equity) / oos_equity[:-1]
    oos_ret = oos_ret[np.isfinite(oos_ret)]
    if len(oos_ret) == 0:
        oos_cagr = 0
        oos_sharpe = 0
        oos_maxdd = 0
    else:
        # CAGR
        oos_years = (len(oos_equity)-1) / 252.0
        oos_cagr = (oos_equity[-1] / oos_equity[0])**(1/oos_years) - 1 if oos_years>0 else 0
        # Sharpe
        oos_sharpe = np.mean(oos_ret) / np.std(oos_ret) * np.sqrt(252) if np.std(oos_ret) > 0 else 0
        # MaxDD
        oos_roll_max = np.maximum.accumulate(oos_equity)
        oos_drawdown = (oos_equity - oos_roll_max) / oos_roll_max
        oos_maxdd = np.min(oos_drawdown)
    oos_results[name] = {'CAGR': oos_cagr, 'Sharpe': oos_sharpe, 'MaxDD': oos_maxdd, 'Final': oos_equity[-1]}

print(f"{'Scheme':<12} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8} {'Final':>10}")
print("-"*60)
for name in schemes:
    m = oos_results[name]
    print(f"{name:<12} {m['CAGR']:>7.2%} {m['Sharpe']:>7.2f} {m['MaxDD']:>7.2%} {m['Final']:>10.0f}")
print("-"*60)

# Determine if any scheme beats equal-weight OOS on risk-adjusted terms (Sharpe) and/or lower MaxDD
eq_sharpe = oos_results['EqualWeight']['Sharpe']
eq_dd = oos_results['EqualWeight']['MaxDD']
print("\nOOS Comparison vs EqualWeight:")
for name in ['InvVol', 'RiskParity', 'RollingSharpe']:
    sharpe = oos_results[name]['Sharpe']
    dd = oos_results[name]['MaxDD']
    better_sharpe = sharpe > eq_sharpe
    better_dd = dd > eq_dd  # remember MaxDD is negative, so higher (less negative) is better
    print(f"{name:<12} Sharpe: {sharpe:>6.2f} ({'+' if better_sharpe else ''}{sharpe-eq_sharpe:>+5.2f}) "
          f"MaxDD: {dd:>6.2%} ({'+' if better_dd else ''}{dd-eq_dd:>+5.2%})")

print("\n" + "="*60)
print("APPENDING TO FINDINGS.md")
print("="*60)
# Prepare findings to append
findings_text = f"""
## Pillar Allocation Test (Cost-Aware, Monthly Rebalancing)
**Date**: {datetime.date.today()}
**Data**: Nasdaq (S1+S4+S5L+S5S), Gold (FVG), BTC (Sweep) daily P&L from 2019-01-10 to 2025-10-10
**Method**: Monthly rebalancing on first day of month, 5 bps turnover cost, no look-ahead bias.
**Validation**: In-sample (2019-2022) vs Out-of-sample (2023-2025)

### Full Period Results (2019-2025)
| Scheme | CAGR | Sharpe | MaxDD | Final Equity |
|--------|------|--------|-------|--------------|
"""
for name in schemes:
    m = compute_metrics(results[name]['equity'], results[name]['daily_net'])
    findings_text += f"| {name} | {m['CAGR']:>6.2%} | {m['Sharpe']:>6.2f} | {m['MaxDD']:>6.2%} | {m['FinalEquity']:>9.0f} |\n"

findings_text += "\n### OOS Results (2023-2025)\n"
findings_text += "| Scheme | CAGR | Sharpe | MaxDD | Final Equity |\n"
findings_text += "|--------|------|--------|-------|--------------|\n"
for name in schemes:
    m = oos_results[name]
    findings_text += f"| {name} | {m['CAGR']:>6.2%} | {m['Sharpe']:>6.2f} | {m['MaxDD']:>6.2%} | {m['Final']:>9.0f} |\n"

findings_text += "\n### OOS Performance Relative to EqualWeight\n"
findings_text += "| Scheme | Δ Sharpe | Δ MaxDD | Verdict |\n"
findings_text += "|--------|----------|---------|---------|\n"
for name in ['InvVol', 'RiskParity', 'RollingSharpe']:
    sharpe = oos_results[name]['Sharpe']
    dd = oos_results[name]['MaxDD']
    delta_sharpe = sharpe - eq_sharpe
    delta_dd = dd - eq_dd  # positive means less negative (better)
    verdict = "Improves" if (delta_sharpe > 0 and delta_dd > 0) else "Mixed" if (delta_sharpe > 0 or delta_dd > 0) else "Worse"
    findings_text += f"| {name} | {delta_sharpe:>+6.2f} | {delta_dd:>+6.2%} | {verdict} |\n"

# Append to FINDINGS.md
with open('/Users/colindayer/nas100_backtest/FINDINGS.md', 'a') as f:
    f.write(findings_text)

print("Findings appended to FINDINGS.md")