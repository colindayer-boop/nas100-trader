"""
cfd_validate.py — Does the Nasdaq/gold edge SURVIVE the move to prop instruments?

FTMO trades CFDs, not ETFs: US100≈NQ (Nasdaq futures), XAUUSD≈GC (gold futures).
We established edges port across wrappers of the SAME index (QQQ↔NQ) but NOT
across different markets. This CONFIRMS it on real data: run the exact S1 Asian-
sweep logic (from verify_liveness.py) on NQ vs QQQ over the same 2024-26 window,
backtest both with identical % stops, and compare. If NQ tracks QQQ → the pillar
is prop-portable. Gold: same test, GC vs GLD.

Futures actually have FULL overnight data (the Asian session the ETF only partly
sees), so this is a fair-or-better test.
"""
import pandas as pd, numpy as np, pytz, warnings
import yfinance as yf
from verify_liveness import s1_signals, load_hourly
warnings.filterwarnings("ignore")
eastern = pytz.timezone("US/Eastern")

STOP, RR = 0.015, 3.0      # S1 stop / reward (same as live)
WIN_START = "2024-02-05"   # common window (futures hourly history start)


def load_future(ticker):
    d = yf.download(ticker, period="730d", interval="1h", progress=False, auto_adjust=True)
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d = d.tz_convert(eastern) if d.index.tz else d.tz_localize("UTC").tz_convert(eastern)
    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return d


def load_etf_window(sym):
    d = load_hourly(sym)
    return d[d.index >= pd.Timestamp(WIN_START, tz=eastern)]


def backtest(df, sig):
    """Enter at signal close; exit on +RR*STOP (win) or -STOP (loss). No overlap."""
    df = df.copy(); idx = df.index
    sig = sig.reindex(idx).fillna(False)
    trades = []; i = 0; n = len(df)
    closes, highs, lows = df["Close"].values, df["High"].values, df["Low"].values
    sigv = sig.values
    while i < n:
        if not sigv[i]:
            i += 1; continue
        entry = closes[i]; stop = entry*(1-STOP); tgt = entry*(1+STOP*RR)
        j = i+1; outcome = None
        while j < n:
            if lows[j] <= stop: outcome = -STOP; break
            if highs[j] >= tgt: outcome = STOP*RR; break
            j += 1
        if outcome is None: break          # open at data end
        trades.append(outcome); i = j+1     # flat until trade resolves
    t = pd.Series(trades)
    if len(t) == 0: return dict(n=0, wr=0, ret=0, pf=0)
    pf = t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else 99.9
    eq = (1+t).prod()-1
    return dict(n=len(t), wr=(t>0).mean(), ret=eq, pf=pf)


def compare(label, etf_sym, fut_ticker):
    etf = load_etf_window(etf_sym)
    fut = load_future(fut_ticker)
    fut["Date"] = fut.index.date
    e_sig, f_sig = s1_signals(etf), s1_signals(fut)
    e, f = backtest(etf, e_sig), backtest(fut, f_sig)
    print(f"\n{label}  (window {WIN_START} → now, S1 Asian-sweep, {STOP:.1%} stop {RR:.0f}:1)")
    print(f"  {etf_sym:<6} (ETF)     : signals~{int(e_sig.sum()):>4} | trades {e['n']:>3} | "
          f"win {e['wr']:.0%} | PF {e['pf']:.2f} | ret {e['ret']:+.1%}")
    print(f"  {fut_ticker:<6} (futures): signals~{int(f_sig.sum()):>4} | trades {f['n']:>3} | "
          f"win {f['wr']:.0%} | PF {f['pf']:.2f} | ret {f['ret']:+.1%}")
    if e['n'] and f['n']:
        verdict = ("✅ PORTS — futures tracks ETF" if (f['wr'] >= e['wr']-0.10 and f['pf'] >= 1.0)
                   else "⚠️ DIVERGES — re-examine before prop deploy")
        print(f"  >>> {verdict}")
    else:
        print("  >>> insufficient trades to judge")


print("="*70)
print("CFD/FUTURES PORTABILITY CHECK — does the edge survive the instrument swap?")
print("="*70)
compare("NASDAQ pillar  (QQQ → US100/NQ)", "QQQ", "NQ=F")
compare("GOLD pillar    (GLD → XAUUSD/GC)", "GLD", "GC=F")
print("\nNote: same % stops, same logic, same window. Futures include full")
print("overnight (Asian) data the ETF lacks, so signal counts can differ — what")
print("matters is whether win-rate / profit-factor hold up on the prop instrument.")
