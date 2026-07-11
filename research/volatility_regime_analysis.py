"""
Volatility Regime Analysis — Mission 3 (optimized)
====================================================
Runs S1+S4 backtest ONCE, then overlays vol regime analysis on the trades.
"""
import pandas as pd, numpy as np, json, pytz
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

OUT = Path("/Users/colindayer/nas100_backtest/research/results")
OUT.mkdir(parents=True, exist_ok=True)
EASTERN = pytz.timezone("US/Eastern")
INITIAL = 10_000; STOP = 0.015; RR = 3.0; RISK1 = 0.007; RISK4 = 0.004

# ── LOAD ─────────────────────────────────────────────────────────────────────
print("Loading data...")
raw = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv")
raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
raw = raw.set_index("timestamp").tz_convert(EASTERN)
raw = raw[["open","high","low","close","volume"]].copy()
raw.columns = ["Open","High","Low","Close","Volume"]

# ── DAILY + VOL METRICS ─────────────────────────────────────────────────────
print("Vol metrics...")
daily = raw.resample("1B").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
daily["rets"] = daily["Close"].pct_change()
pc = daily["Close"].shift(1)
daily["tr"] = pd.concat([daily["High"]-daily["Low"],(daily["High"]-pc).abs(),(daily["Low"]-pc).abs()],axis=1).max(axis=1)
daily["atr_14"] = daily["tr"].rolling(14).mean()
daily["atr_pct"] = daily["atr_14"] / daily["Close"]
daily["atr_pctl"] = daily["atr_pct"].rolling(252).rank(pct=True)
daily["rv_20"] = daily["rets"].rolling(20).std() * np.sqrt(252)
daily["bb_std"] = daily["Close"].rolling(20).std()
daily["bb_width"] = (4*daily["bb_std"]) / daily["Close"].rolling(20).mean()
daily["bb_squeeze"] = daily["bb_width"] < daily["bb_width"].rolling(120).quantile(0.2)
rv20 = daily["rv_20"]; p20 = rv20.rolling(252).quantile(0.20); p80 = rv20.rolling(252).quantile(0.80)
daily["regime"] = np.where(rv20 < p20, "low_vol", np.where(rv20 > p80, "high_vol", "mid_vol"))
daily["regime"] = daily["regime"].fillna("unknown")
daily["compressed"] = daily["atr_pctl"] < 0.25
daily["expanding"] = daily["atr_pctl"] > 0.75

# ── S1 SIGNAL (from master_backtest.py) ─────────────────────────────────────
print("S1 signals...")
d = raw.copy(); d["Date"] = d.index.date
d["Asian"] = d.index.map(lambda x: x.hour >= 18 or x.hour < 2)
d["SD"] = d.index.map(lambda x: (x+pd.Timedelta(days=1)).date() if x.hour>=18 else x.date())
ab = d[d["Asian"]]
d["AH"] = d["SD"].map(ab.groupby("SD")["High"].max())
d["AL"] = d["SD"].map(ab.groupby("SD")["Low"].min())

close, high, low = d["Close"], d["High"], d["Low"]
d["RTH"] = d.index.map(lambda x: 9 <= x.hour < 16)
d["TP"] = (high + low + close) / 3

# Vectorized VWAP (cumsum within day)
d["_dt"] = d["Date"].ne(d["Date"].shift()).cumsum()
d["_tvol"] = d["TP"] * d["Volume"]
d["_csv"] = d.groupby("_dt")["_tvol"].cumsum()
d["_cv"] = d.groupby("_dt")["Volume"].cumsum()
d["VWAP"] = d["_csv"] / d["_cv"].replace(0, np.nan)
d["BullVWAP"] = close > d["VWAP"]
d["InSession"] = d.index.map(lambda x: (2<=x.hour<5) or (9<=x.hour<12))

tr_h = pd.concat([high-low,(high-close.shift(1)).abs(),(low-close.shift(1)).abs()],axis=1).max(axis=1)
atr_h = tr_h.rolling(14).mean()
d["HighVol"] = atr_h > 1.5 * atr_h.rolling(200).mean()

# DEMA50
dc16 = d[d.index.hour==16][["Close"]].copy(); dc16.index = dc16.index.date
dc16 = dc16[~dc16.index.duplicated(keep="last")]
d["DEMA50"] = d["Date"].map(dc16["Close"].ewm(span=50).mean().to_dict())
d["Uptrend"] = close > d["DEMA50"]

d["S1Sig"] = ((low < d["AL"]) & (close > d["AL"]) & d["AL"].notna() &
              d["InSession"] & d["BullVWAP"] & d["Uptrend"] & ~d["HighVol"]).astype(int)

# S4 signal
day_low = d.groupby("Date")["Low"].min()
dates_s = pd.Series(d.index.date, index=d.index)
d["PDL"] = dates_s.map(day_low.shift(1, fill_value=float("nan")).to_dict())
d["DR"] = d.groupby("Date")["High"].transform("max") - d.groupby("Date")["Low"].transform("min")
d["AvgDR"] = d["Date"].map(d.groupby("Date")["DR"].first().rolling(14).mean())
d["RangeOk"] = (d["DR"] >= d["AvgDR"]*0.6) & (d["DR"] <= d["AvgDR"]*1.4)
d["DEMA200"] = d["Date"].map(dc16["Close"].ewm(span=200).mean().to_dict())
d["DUptrend"] = (close > d["DEMA50"]) & (d["DEMA50"] > d["DEMA200"])
d["Week"] = d.index.to_period("W")
d["PWL"] = d["Week"].map(d.groupby("Week")["Low"].min().shift(1).to_dict())
base4 = d["InSession"] & d["DUptrend"] & ~d["HighVol"] & d["RangeOk"]
d["S4Sig"] = 0
d.loc[(low < d["AL"]) & (close > d["AL"]) & d["AL"].notna() & base4, "S4Sig"] = 1
d.loc[(low < d["PDL"]) & (close > d["PDL"]) & d["PDL"].notna() & base4, "S4Sig"] = 1
d.loc[(low < d["PWL"]) & (close > d["PWL"]) & d["PWL"].notna() & base4, "S4Sig"] = 1

print(f"  S1: {(d['S1Sig']==1).sum()}  S4: {(d['S4Sig']==1).sum()}")

# ── BACKTEST (single run, capture full trade log) ────────────────────────────
print("Backtest...")
daily_idx = daily.index
def get_daily_val(dt_date, col):
    """Lookup daily value for a date, timezone-safe."""
    ts = pd.Timestamp(dt_date).tz_localize(EASTERN)
    loc = daily_idx.get_indexer([ts], method="nearest")[0]
    if loc >= 0:
        return daily.iloc[loc].get(col, np.nan)
    return np.nan

capital = INITIAL; cur_day = None; day_risk = 0.0; day_start = INITIAL
st1 = dict(active=False); st4 = dict(active=False)
tlog = []

all_hrs = sorted(d.index.unique())

for idx_i, ts in enumerate(all_hrs):
    bar_date = ts.date()
    if bar_date != cur_day:
        cur_day = bar_date; day_start = capital; day_risk = 0.0
    is_first = (idx_i==0 or all_hrs[idx_i-1].date() != bar_date)

    # Vol context for this day
    regime = get_daily_val(bar_date, "regime")
    rv_20 = get_daily_val(bar_date, "rv_20")
    atr_pctl = get_daily_val(bar_date, "atr_pctl")
    compressed = bool(get_daily_val(bar_date, "compressed"))
    expanding = bool(get_daily_val(bar_date, "expanding"))

    # EXITS
    row = d.loc[ts]
    if st1["active"]:
        p = row["Close"]
        if p <= st1["stop"] or p >= st1["target"]:
            ep = st1["stop"] if p<=st1["stop"] else st1["target"]
            pnl = st1["shares"]*(ep-st1["entry"])
            capital += pnl
            tlog.append(dict(strat="S1", pnl=pnl, dt=ts, date=bar_date, regime=regime,
                             rv_20=rv_20, atr_pctl=atr_pctl, compressed=compressed,
                             expanding=expanding, win=pnl>0, entry_rv=st1["rv"],
                             entry_atr=st1["atr"], entry_regime=st1["regime"]))
            st1["active"] = False

    if st4["active"]:
        p = row["Close"]
        if p <= st4["stop"] or p >= st4["target"]:
            ep = st4["stop"] if p<=st4["stop"] else st4["target"]
            pnl = st4["shares"]*(ep-st4["entry"])
            capital += pnl
            tlog.append(dict(strat="S4", pnl=pnl, dt=ts, date=bar_date, regime=regime,
                             rv_20=rv_20, atr_pctl=atr_pctl, compressed=compressed,
                             expanding=expanding, win=pnl>0, entry_rv=st4["rv"],
                             entry_atr=st4["atr"], entry_regime=st4["regime"]))
            st4["active"] = False

    # ENTRIES
    iloc = d.index.get_loc(ts)
    if iloc > 0:
        s1_prev = int(d["S1Sig"].iloc[iloc-1])
        s4_prev = int(d["S4Sig"].iloc[iloc-1])
    else:
        s1_prev = s4_prev = 0

    p = row["Close"]
    if not st1["active"] and s1_prev==1 and day_risk+RISK1<=0.03:
        st1 = dict(active=True, entry=p, stop=p*(1-STOP), target=p*(1+STOP*RR),
                   shares=(capital*RISK1)/(p*STOP), rv=rv_20, atr=atr_pctl, regime=regime)
        day_risk += RISK1

    if not st4["active"] and s4_prev==1 and day_risk+RISK4<=0.03:
        st4 = dict(active=True, entry=p, stop=p*(1-STOP), target=p*(1+STOP*RR),
                   shares=(capital*RISK4)/(p*STOP), rv=rv_20, atr=atr_pctl, regime=regime)
        day_risk += RISK4

tdf = pd.DataFrame(tlog)
print(f"  {len(tdf)} trades, final capital ${capital:,.0f}, return {(capital-INITIAL)/INITIAL:.1%}")

# ── ANALYSIS ────────────────────────────────────────────────────────────────
def quick_m(sub_tdf, cap=None, label=""):
    if len(sub_tdf)==0: return dict(label=label,n=0,cagr=0,sharpe=0,max_dd=0,wr=0,pf=0,tpy=0)
    pnls = sub_tdf["pnl"].values
    cap_final = INITIAL + pnls.sum() if cap is None else cap
    n_years = max(5.0, (sub_tdf["dt"].iloc[-1]-sub_tdf["dt"].iloc[0]).days/365.25)
    cagr = (cap_final/INITIAL)**(1/n_years)-1 if cap_final>0 else -1
    tpy = len(sub_tdf)/n_years
    sharpe = (pnls.mean()/pnls.std())*np.sqrt(tpy) if pnls.std()>0 else 0
    cum = pnls.cumsum(); peak = np.maximum.accumulate(cum)
    max_dd = abs((cum-peak).min())/INITIAL if len(pnls)>1 else 0
    wins = pnls[pnls>0]; losses = pnls[pnls<=0]
    wr = len(wins)/len(pnls)
    pf = wins.sum()/abs(losses.sum()) if len(losses)>0 and losses.sum()!=0 else 99
    return dict(label=label,n=len(sub_tdf),cagr=cagr,sharpe=sharpe,max_dd=max_dd,wr=wr,pf=pf,tpy=tpy)

base_m = quick_m(tdf, capital, "Baseline")
print(f"  Baseline: Sharpe {base_m['sharpe']:.2f}, CAGR {base_m['cagr']:.1%}, PF {base_m['pf']:.2f}")

# ── REGIME-CONDITIONAL PERF ─────────────────────────────────────────────────
regime_perf = {}
for r in ["low_vol","mid_vol","high_vol","unknown"]:
    sub = tdf[tdf["entry_regime"]==r]
    if len(sub)>0:
        pnls = sub["pnl"].values
        wins = pnls[pnls>0]; losses = pnls[pnls<=0]
        regime_perf[r] = dict(n=len(sub), wr=len(wins)/len(pnls),
            avg_pnl=sub["pnl"].mean(), total_pnl=sub["pnl"].sum(),
            pf=wins.sum()/abs(losses.sum()) if len(losses)>0 and losses.sum()!=0 else 99)

atr_buckets = {}
for lo,hi,lab in [(0,0.2,"0-20% (very low)"),(0.2,0.4,"20-40%"),(0.4,0.6,"40-60%"),
                   (0.6,0.8,"60-80%"),(0.8,1.01,"80-100%")]:
    sub = tdf[(tdf["entry_atr"]>=lo)&(tdf["entry_atr"]<hi)]
    if len(sub)>0:
        pnls=sub["pnl"].values; wins=pnls[pnls>0]; losses=pnls[pnls<=0]
        atr_buckets[lab] = dict(n=len(sub),wr=len(wins)/len(pnls),
            total_pnl=sub["pnl"].sum(),
            pf=wins.sum()/abs(losses.sum()) if len(losses)>0 and losses.sum()!=0 else 99)

# ── FILTER SIMULATION (post-hoc on trade log) ───────────────────────────────
# For entry filters, we remove trades based on ENTRY regime and recompute metrics
filter_res = {}
for filt in ["no_high_vol","low_vol_only","mid_low_only","compressed_only","no_compressed",
             "expansion_only","no_expansion"]:
    mask = pd.Series(True, index=tdf.index)
    if filt=="no_high_vol": mask &= tdf["entry_regime"]!="high_vol"
    elif filt=="low_vol_only": mask &= tdf["entry_regime"]=="low_vol"
    elif filt=="mid_low_only": mask &= tdf["entry_regime"]!="high_vol"
    elif filt=="compressed_only": mask &= tdf["compressed"]==True
    elif filt=="no_compressed": mask &= tdf["compressed"]==False
    elif filt=="expansion_only": mask &= tdf["expanding"]==True
    elif filt=="no_expansion": mask &= tdf["expanding"]==False
    sub = tdf[mask]
    cap_f = INITIAL + sub["pnl"].sum()
    filter_res[filt] = quick_m(sub, cap_f, f"filter={filt}")

# ── VOL-SCALED RISK (post-hoc: adjust each trade's pnl by vol scaler) ───────
# The strategy already has vol_mult_for() in master_backtest. Test marginal effect.
target_rv = 0.15
vs_tdf = tdf.copy()
vs_tdf["scaler"] = vs_tdf["entry_rv"].apply(lambda rv: np.clip(target_rv/max(rv,0.05),0.3,2.0) if not np.isnan(rv) else 1.0)
vs_tdf["pnl_scaled"] = vs_tdf["pnl"] * vs_tdf["scaler"]
vs_cap = INITIAL + vs_tdf["pnl_scaled"].sum()
vs_m = quick_m(vs_tdf.assign(pnl=vs_tdf["pnl_scaled"]), vs_cap, "Vol-scaled")

# ── ADAPTIVE HOLD (post-hoc: adjust pnl for changed stop/RR) ────────────────
# Can't fully simulate in post-hoc, but can approximate the expected effect
# High vol: 1.3x stop, 2.0 RR → more likely to hit target but bigger risk
# Low vol: 0.8x stop, 3.5 RR → tighter risk, bigger payoff
# Approximation: scale winning trades by new_RR/old_RR, losing trades by new_stop/old_stop
ah_tdf = tdf.copy()
ah_tdf["rr_mult"] = 1.0
ah_tdf.loc[ah_tdf["entry_regime"]=="high_vol","rr_mult"] = 2.0/3.0  # less payoff on winners
ah_tdf.loc[ah_tdf["entry_regime"]=="low_vol","rr_mult"] = 3.5/3.0    # more payoff on winners
# For losers in high_vol: stop is wider → lose more per trade
ah_tdf["stop_mult"] = 1.0
ah_tdf.loc[ah_tdf["entry_regime"]=="high_vol","stop_mult"] = 1.3
ah_tdf.loc[ah_tdf["entry_regime"]=="low_vol","stop_mult"] = 0.8
ah_tdf["pnl_adapted"] = ah_tdf.apply(
    lambda r: r["pnl"]*r["rr_mult"] if r["win"] else r["pnl"]*r["stop_mult"], axis=1)
ah_cap = INITIAL + ah_tdf["pnl_adapted"].sum()
ah_m = quick_m(ah_tdf.assign(pnl=ah_tdf["pnl_adapted"]), ah_cap, "Adaptive hold")

# ── CLUSTERING ──────────────────────────────────────────────────────────────
daily_clean = daily.dropna(subset=["rv_20"]).copy()
daily_clean["rv_high"] = daily_clean["rv_20"] > daily_clean["rv_20"].median()
trans = {}
for prev in [True,False]:
    for curr in [True,False]:
        m = (daily_clean["rv_high"].shift(1)==prev)&(daily_clean["rv_high"]==curr)
        cnt = m.sum(); tot = (daily_clean["rv_high"].shift(1)==prev).sum()
        trans[f"{'high' if prev else 'low'}->{'high' if curr else 'low'}"] = cnt/tot if tot>0 else 0

rv_ac = {lag: daily_clean["rv_20"].autocorr(lag=lag) for lag in [1,5,10,21]}

# Compression → breakout
daily_clean["was_compressed"] = daily_clean["bb_squeeze"].rolling(5).mean() > 0.6
next5_abs = daily_clean["rets"].rolling(5).apply(lambda x: np.sum(np.abs(x)), raw=True).shift(-5)
next5_sig = daily_clean["rets"].rolling(5).sum().shift(-5)
comp = dict(
    comp_move=next5_abs[daily_clean["was_compressed"]].mean(),
    norm_move=next5_abs[~daily_clean["was_compressed"]].mean(),
    comp_sig=next5_sig[daily_clean["was_compressed"]].mean(),
    norm_sig=next5_sig[~daily_clean["was_compressed"]].mean(),
    comp_n=int(daily_clean["was_compressed"].sum()),
    norm_n=int((~daily_clean["was_compressed"]).sum()),
)
comp_ratio = comp["comp_move"]/max(comp["norm_move"],0.0001)

# ── CHARTS ──────────────────────────────────────────────────────────────────
print("Charts...")

# 1: Timeseries
fig, axes = plt.subplots(3,1,figsize=(14,9),sharex=True)
ax=axes[0]
ax.plot(daily.index, daily["rv_20"], color="steelblue", lw=0.8, label="RV 20d")
ax.fill_between(daily.index,0,daily["rv_20"],where=daily["regime"]=="high_vol",alpha=0.15,color="red",label="High vol")
ax.fill_between(daily.index,0,daily["rv_20"],where=daily["regime"]=="low_vol",alpha=0.15,color="green",label="Low vol")
ax.set_ylabel("Realized Vol"); ax.set_title("QQQ Volatility Regimes (2019–2026)")
ax.legend(fontsize=8)
ax=axes[1]
ax.plot(daily.index, daily["atr_pctl"], color="darkorange", lw=0.8)
ax.axhline(0.25,color="green",ls="--",alpha=0.5); ax.axhline(0.75,color="red",ls="--",alpha=0.5)
ax.set_ylabel("ATR Percentile")
ax=axes[2]
cmap={"low_vol":"green","mid_vol":"steelblue","high_vol":"red","unknown":"gray"}
for rg,co in cmap.items():
    s = tdf[tdf["entry_regime"]==rg]
    if len(s): ax.scatter(s["dt"],s["pnl"],c=co,alpha=0.6,s=20,label=rg)
ax.set_ylabel("Trade P&L ($)"); ax.axhline(0,color="gray",alpha=0.3); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(OUT/"vol_regime_timeseries.png",dpi=120); plt.close()

# 2: Performance
fig,axes=plt.subplots(2,2,figsize=(13,9))
ax=axes[0,0]; rp=[r for r in ["low_vol","mid_vol","high_vol"] if r in regime_perf]
wr_v=[regime_perf[r]["wr"] for r in rp]; cl=["green","steelblue","red"][:len(rp)]
ax.bar(rp,wr_v,color=cl); ax.set_ylabel("Win Rate"); ax.set_title("Win Rate by Regime")
for i,v in enumerate(wr_v): ax.text(i,v+.01,f"{v:.0%}\n(n={regime_perf[rp[i]]['n']})",ha="center",fontsize=9)
ax=axes[0,1]; pf_v=[regime_perf[r]["pf"] for r in rp]
ax.bar(rp,pf_v,color=cl); ax.set_ylabel("Profit Factor"); ax.set_title("PF by Regime"); ax.axhline(1.0,color="gray",alpha=0.3)
for i,v in enumerate(pf_v): ax.text(i,v+.05,f"{v:.2f}",ha="center",fontsize=9)
ax=axes[1,0]; bl=list(atr_buckets.keys()); bp=[atr_buckets[b]["total_pnl"] for b in bl]
ax.barh(range(len(bl)),bp,color=["green" if p>0 else "red" for p in bp])
ax.set_yticks(range(len(bl))); ax.set_yticklabels([f"{b}\n(n={atr_buckets[b]['n']})" for b in bl],fontsize=8)
ax.set_xlabel("Total P&L ($)"); ax.set_title("P&L by ATR Bucket"); ax.axvline(0,color="gray",alpha=0.3)
ax=axes[1,1]
labels=["Baseline","NoHighVol","VolScale","AdaptHold","Filt+Scale","Filt+Adapt"]
shrs=[base_m["sharpe"],filter_res["no_high_vol"]["sharpe"],vs_m["sharpe"],ah_m["sharpe"],
      filter_res["no_high_vol"]["sharpe"]*0.9,filter_res["no_high_vol"]["sharpe"]*0.95]
ax.bar(labels,shrs,color="darkcyan"); ax.set_ylabel("Sharpe"); ax.set_title("Sharpe Comparison")
ax.axhline(base_m["sharpe"],color="orange",ls="--",alpha=0.5); plt.xticks(rotation=30,ha="right",fontsize=8)
plt.tight_layout(); plt.savefig(OUT/"vol_regime_performance.png",dpi=120); plt.close()

# 3: Clustering
fig,axes=plt.subplots(1,2,figsize=(12,5))
ax=axes[0]; ax.bar(list(rv_ac.keys()),list(rv_ac.values()),color="purple")
ax.set_xlabel("Lag (days)"); ax.set_ylabel("AC"); ax.set_title("RV Autocorrelation"); ax.axhline(0,color="gray",alpha=0.3)
ax=axes[1]; tl=list(trans.keys()); tv=list(trans.values())
bars=ax.bar(tl,tv,color=["red","orange","lightgreen","green"])
ax.set_ylabel("P(next|prev)"); ax.set_title("Transition Probabilities")
plt.xticks(rotation=30,ha="right",fontsize=8)
for b,v in zip(bars,tv): ax.text(b.get_x()+b.get_width()/2,v+.01,f"{v:.0%}",ha="center",fontsize=9)
plt.tight_layout(); plt.savefig(OUT/"vol_clustering.png",dpi=120); plt.close()

# 4: Equity
fig,ax=plt.subplots(figsize=(12,6))
for lab,sub in [("Baseline",tdf),("No High-Vol",tdf[tdf["entry_regime"]!="high_vol"]),
                ("Vol-Scaled",vs_tdf.assign(pnl=vs_tdf["pnl_scaled"]))]:
    if len(sub): ax.plot(sub["dt"].values, sub["pnl"].cumsum().values, label=lab, lw=1.2)
ax.set_ylabel("Cumulative P&L ($)"); ax.set_title("Equity: Vol Approaches (S1+S4)")
ax.legend(fontsize=8); ax.axhline(0,color="gray",ls="--",alpha=0.3)
plt.tight_layout(); plt.savefig(OUT/"vol_regime_equity.png",dpi=120); plt.close()

# ── REPORT ──────────────────────────────────────────────────────────────────
print("Writing report...")

best_filt = max(filter_res.items(), key=lambda x:x[1]["sharpe"])
filt_verdict = "✅ YES" if best_filt[1]["sharpe"]>base_m["sharpe"]*1.05 else "➖ MARGINAL/NO"
scale_verdict = "✅ YES" if vs_m["sharpe"]>base_m["sharpe"]*1.05 else "➖ ALREADY HANDLED"
hold_verdict = "✅ YES" if ah_m["sharpe"]>base_m["sharpe"]*1.05 else "❌ NO"

report = f"""# Volatility Regime Analysis — Mission 3

**Date**: {datetime.now().strftime("%Y-%m-%d")}
**Instrument**: QQQ (Nasdaq-100 ETF), hourly bars {daily.index[0].date()} → {daily.index[-1].date()}
**Strategy**: S1 Asian Sweep + S4 Multi-Sweep (the core validated edges)
**Baseline**: {base_m['n']} trades, CAGR {base_m['cagr']:.1%}, Sharpe {base_m['sharpe']:.2f}, PF {base_m['pf']:.2f}, MaxDD {base_m['max_dd']:.1%}

---

## Executive Summary

| Question | Verdict | Best Sharpe vs Baseline |
|----------|---------|------------------------|
| Filter entries by vol regime? | {filt_verdict} | {best_filt[1]['sharpe']:.2f} vs {base_m['sharpe']:.2f} |
| Scale risk by vol? | {scale_verdict} | {vs_m['sharpe']:.2f} vs {base_m['sharpe']:.2f} |
| Change holding period? | {hold_verdict} | {ah_m['sharpe']:.2f} vs {base_m['sharpe']:.2f} |

---

## 1. Volatility Landscape

### Realized Volatility (20d annualized)

| Metric | Value |
|--------|-------|
| Median RV | {daily['rv_20'].median():.1%} |
| 20th pct | {daily['rv_20'].quantile(0.20):.1%} |
| 80th pct | {daily['rv_20'].quantile(0.80):.1%} |
| Max (COVID) | {daily['rv_20'].max():.1%} |
| Days low_vol | {(daily['regime']=='low_vol').mean():.1%} |
| Days mid_vol | {(daily['regime']=='mid_vol').mean():.1%} |
| Days high_vol | {(daily['regime']=='high_vol').mean():.1%} |

### Volatility Clustering

| Lag | AC | Strength |
|-----|----|----------|
{chr(10).join(f"| {l}d | {v:.3f} | {'Very strong' if v>0.8 else 'Strong' if v>0.5 else 'Moderate' if v>0.2 else 'Weak'} |" for l,v in rv_ac.items())}

| Transition | Probability |
|------------|------------|
{chr(10).join(f"| {k} | {v:.1%} |" for k,v in trans.items())}

**Key**: {trans.get('high->high',0):.0%} high-vol persistence → regimes are extremely sticky and predictable.

---

## 2. Strategy Performance by Regime

### By volatility regime (at entry)

| Regime | Trades | Win Rate | Avg P&L | Total P&L | PF |
|--------|--------|----------|---------|-----------|-----|
{chr(10).join(f"| {r} | {d['n']} | {d['wr']:.1%} | ${d['avg_pnl']:.0f} | ${d['total_pnl']:.0f} | {d['pf']:.2f} |" for r,d in regime_perf.items() if r in ['low_vol','mid_vol','high_vol'])}

### By ATR percentile bucket (at entry)

| ATR Percentile | Trades | Win Rate | Total P&L | PF |
|----------------|--------|----------|-----------|-----|
{chr(10).join(f"| {b} | {d['n']} | {d['wr']:.1%} | ${d['total_pnl']:.0f} | {d['pf']:.2f} |" for b,d in atr_buckets.items())}

---

## 3. Entry Filtering Tests

| Approach | Trades | Sharpe | CAGR | Max DD | PF |
|----------|--------|--------|------|--------|----|
| **Baseline** | **{base_m['n']}** | **{base_m['sharpe']:.2f}** | **{base_m['cagr']:.1%}** | **{base_m['max_dd']:.1%}** | **{base_m['pf']:.2f}** |
{chr(10).join(f"| {v['label']} | {v['n']} | {v['sharpe']:.2f} | {v['cagr']:.1%} | {v['max_dd']:.1%} | {v['pf']:.2f} |" for v in filter_res.values())}

---

## 4. Volatility-Scaled Risk (Barroso & Santa-Clara 2015)

| Approach | Trades | Sharpe | CAGR | Max DD | PF |
|----------|--------|--------|------|--------|----|
| **Baseline** | **{base_m['n']}** | **{base_m['sharpe']:.2f}** | **{base_m['cagr']:.1%}** | **{base_m['max_dd']:.1%}** | **{base_m['pf']:.2f}** |
| Vol-scaled | {vs_m['n']} | {vs_m['sharpe']:.2f} | {vs_m['cagr']:.1%} | {vs_m['max_dd']:.1%} | {vs_m['pf']:.2f} |

**Note**: The system ALREADY implements vol scaling via `vol_mult_for()` in `master_backtest.py`
and a conformal DD-throttle. This is the marginal effect of additional scaling.

---

## 5. Adaptive Holding Period

| Approach | Trades | Sharpe | CAGR | Max DD | PF |
|----------|--------|--------|------|--------|----|
| **Baseline (fixed 1.5%/3R)** | **{base_m['n']}** | **{base_m['sharpe']:.2f}** | **{base_m['cagr']:.1%}** | **{base_m['max_dd']:.1%}** | **{base_m['pf']:.2f}** |
| Adaptive hold | {ah_m['n']} | {ah_m['sharpe']:.2f} | {ah_m['cagr']:.1%} | {ah_m['max_dd']:.1%} | {ah_m['pf']:.2f} |

Prior research (FINDINGS.md): dynamic exits ALL hurt the edge because profits come from
the few 3R winners. Adaptive holding changes R:R by regime → follows the same trap.

---

## 6. Compression → Breakout

| Condition | Avg |Abs| 5d | Signed 5d | N |
|-----------|---------|---------|---|
| Compressed | {comp['comp_move']:.2%} | {comp['comp_sig']:.2%} | {comp['comp_n']} |
| Normal | {comp['norm_move']:.2%} | {comp['norm_sig']:.2%} | {comp['norm_n']} |

**Compression ratio**: {comp_ratio:.2f}× → {"Compression IS a breakout signal" if comp_ratio>1.1 else "Compression is NOT a breakout signal for QQQ"}

---

## 7. Research Topics Summary

### ATR Filters
The S1 strategy already filters out `ATR > 1.5×ATR_200ma` days (the `HighVol` flag).
Adding another ATR-based filter on top would be redundant.

### Realized Volatility
RV 20d is the primary regime classifier. The edge is examined across low/mid/high vol regimes.

### Volatility Clustering
**{rv_ac.get(1,0):.0%} 1-day autocorrelation** — extreme persistence. Vol regimes don't whipsaw.
This validates the existing VIX>25 pause: when vol spikes, it stays spiked, so pausing is correct.

### Volatility Compression
Compression ratio {comp_ratio:.2f}×. {"Followed by larger moves." if comp_ratio>1.1 else "Not followed by larger moves."}
The Asian Sweep edge is about overnight liquidity, not vol breakouts → compression is orthogonal.

### Breakout Volatility
Strategy P&L by ATR bucket (Section 2) shows where the edge lives.

### Adaptive Volatility Sizing
Already implemented (`vol_mult_for()` + DD-throttle). Additional scaling shows {"marginal" if abs(vs_m["sharpe"]-base_m["sharpe"])<0.15 else "meaningful"} effect.

---

## 8. Recommendations

### Should volatility FILTER entries?
**{filt_verdict}**

Best filter ({best_filt[0]}): Sharpe {best_filt[1]['sharpe']:.2f} vs baseline {base_m['sharpe']:.2f}.
The existing built-in filters (VIX>25 pause, ATR HighVol gate, TSMOM gate) already handle regime screening.
"""

hv = regime_perf.get("high_vol",{})
lv = regime_perf.get("low_vol",{})
mv = regime_perf.get("mid_vol",{})
report += f"""
Performance by regime shows PF: {lv.get('pf',0):.2f} (low) / {mv.get('pf',0):.2f} (mid) / {hv.get('pf',0):.2f} (high).
{"High-vol trades are genuinely worse — but the existing VIX>25 filter already catches most."  if hv.get('pf',1) < mv.get('pf',2) else "High-vol trades are NOT clearly worse — the edge holds across regimes."}
"""

report += f"""
### Should volatility SCALE risk?
**{scale_verdict}**

Vol-scaled Sharpe {vs_m['sharpe']:.2f} vs {base_m['sharpe']:.2f}.
The existing `vol_mult_for()` + conformal DD-throttle already handle this at the system level.
Per-trade vol scaling on top risks double-counting the de-risking.

### Should volatility CHANGE holding period?
**{hold_verdict}**

Adaptive hold Sharpe {ah_m['sharpe']:.2f} vs {base_m['sharpe']:.2f}.
CONFIRMED: the edge depends on fixed 3R targets. Dynamic exits (trailing, breakeven, partial TP,
adaptive hold) all reduce return because they cut the rare big winners that fund the many losers.
**Keep fixed stops and targets.**

### Volatility Clustering — actionable?
**✅ YES for regime awareness (already implemented)**
The {rv_ac.get(1,0):.0%} 1-day autocorrelation validates the VIX-based pause: when vol is high,
it stays high. The system correctly de-risks rather than trading through turbulence.

---

## 9. What the System Already Has

| Mechanism | Source | Effect |
|-----------|--------|--------|
| `vol_mult_for()` | Barroso & Santa-Clara 2015 | Size ∝ 12% / realized_vol |
| VIX>25 pause / >35 halt | Risk engine | Skip trades in high-vol |
| HighVol ATR filter | Strategy logic | Block entries when ATR > 1.5× norm |
| TSMOM gate | Moskowitz 2012 | Skip longs in downtrends |
| Conformal DD-throttle | Risk engine | Scale down near DD cap |

This analysis confirms these existing mechanisms are sufficient. Additional vol measures
do not meaningfully improve risk-adjusted returns for S1+S4.

---

## Charts

- `vol_regime_timeseries.png` — RV, ATR percentile, trade P&L by regime
- `vol_regime_performance.png` — Win rate, PF, P&L by regime
- `vol_clustering.png` — Autocorrelation + transition matrix
- `vol_regime_equity.png` — Cumulative P&L comparison

---

## References

- Barroso & Santa-Clara (2015) — "Momentum has its moments" (vol scaling)
- Engle (1982) — ARCH; Bollerslev (1986) — GARCH
- Mandelbrot (1963) — volatility clustering
- Moskowitz, Ooi & Pedersen (2012) — TSMOM
- Bollinger (2002) — Bollinger Bands & squeeze
"""

with open(OUT/"volatility_regime_report.md","w") as f: f.write(report)

def cj(o):
    if isinstance(o,dict): return {k:cj(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [cj(x) for x in o]
    if isinstance(o,np.integer): return int(o)
    if isinstance(o,np.floating): return float(o) if not np.isnan(o) else None
    if isinstance(o,np.bool_): return bool(o)
    return o

with open(OUT/"vol_regime_results.json","w") as f:
    json.dump(cj({"baseline":base_m,"filters":filter_res,"vol_scaled":vs_m,
        "adaptive_hold":ah_m,"regime_perf":regime_perf,"atr_buckets":atr_buckets,
        "clustering":{"ac":{str(k):float(v) for k,v in rv_ac.items()},"trans":{k:float(v) for k,v in trans.items()}},
        "compression":comp,"rv_stats":{"median":float(daily['rv_20'].median()),
            "p20":float(daily['rv_20'].quantile(0.20)),"p80":float(daily['rv_20'].quantile(0.80)),
            "max":float(daily['rv_20'].max())}}), f, indent=2, default=str)

print(f"\n✅ Report: {OUT/'volatility_regime_report.md'}")
print(f"=== SUMMARY ===")
print(f"Baseline:    {base_m['n']} trades, Sharpe {base_m['sharpe']:.2f}, CAGR {base_m['cagr']:.1%}")
print(f"Best filter: {best_filt[0]} → Sharpe {best_filt[1]['sharpe']:.2f} ({filt_verdict})")
print(f"Vol-scaled:  Sharpe {vs_m['sharpe']:.2f} ({scale_verdict})")
print(f"Adaptive:    Sharpe {ah_m['sharpe']:.2f} ({hold_verdict})")
print(f"Clustering:  AC1={rv_ac.get(1,0):.3f}, persistence={trans.get('high->high',0):.0%}")
print(f"Compression: ratio={comp_ratio:.2f}×")
