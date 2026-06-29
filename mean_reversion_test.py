"""
mean_reversion_test.py — Validate a MEAN-REVERSION pillar through the full gauntlet.

We have ZERO mean-reversion exposure today (all pillars are momentum/breakout).
The research doc found mean reversion the most robust category. We test it on OUR
data, with costs, and apply the same 6 filters the doc used — plus a yearly
out-of-sample breakdown so we see if it holds forward, not just in aggregate.

Two variants on QQQ (and SPY/IWM as confirmation):
  A) Doc Prompt 1  : 1h RSI(14)<30 & close>200EMA → long; exit RSI>55 / +3% / -1.5% stop
  B) Classic RSI-2 : daily RSI(2)<10 & close>200SMA → long; exit close>5d SMA / -3% stop

Pass requires (Harvey-Liu-Zhu / doc filters):
  OOS Sharpe>0.5, maxDD>-35%, OOS Sharpe<2.5, OOS<=IS*1.3+0.5, >=30 trades, IS Sharpe>0
"""
import pandas as pd, numpy as np, pytz, warnings
warnings.filterwarnings("ignore")

SLIP = 0.0004          # round-trip cost for liquid ETF (~2bp each side + spread)
eastern = pytz.timezone("US/Eastern")
ANN_H = np.sqrt(252 * 6.5)   # hourly bars/yr (RTH)
ANN_D = np.sqrt(252)


def load(sym):
    f = f"{sym.lower()}_hourly_7y.csv"
    df = pd.read_csv(f)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").tz_convert(eastern)
    if "symbol" in df: df = df[df["symbol"] == sym]
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    # regular trading hours only
    return df[(df.index.hour >= 9) & (df.index.hour < 16)]


def rsi(s, n):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def metrics(trades, rets, ann):
    """trades=list of per-trade returns; rets=per-bar equity returns for Sharpe."""
    t = pd.Series(trades)
    if len(t) == 0:
        return dict(n=0, wr=0, ret=0, sharpe=0, dd=0)
    eq = (1 + t).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    r = pd.Series(rets)
    sharpe = (r.mean() / r.std() * ann) if r.std() > 0 else 0
    return dict(n=len(t), wr=(t > 0).mean(), ret=eq.iloc[-1] - 1,
                sharpe=sharpe, dd=dd)


def backtest_intraday(df, rsi_buy=30, rsi_exit=55, tp=0.03, sl=0.015):
    """Variant A — doc Prompt 1 on hourly bars."""
    c = df["Close"]
    df = df.assign(RSI=rsi(c, 14), EMA200=c.ewm(span=200).mean())
    trades, bar_ret = [], []
    in_t = False; entry = 0.0
    for i in range(200, len(df)):
        px = df["Close"].iloc[i]
        if in_t:
            ret = px / entry - 1
            bar_ret.append(df["Close"].iloc[i] / df["Close"].iloc[i-1] - 1)
            hit = ret <= -sl or ret >= tp or df["RSI"].iloc[i] > rsi_exit
            if hit:
                trades.append(ret - SLIP); in_t = False
        else:
            bar_ret.append(0.0)
            if df["RSI"].iloc[i] < rsi_buy and px > df["EMA200"].iloc[i]:
                in_t = True; entry = px
    return trades, bar_ret


def backtest_daily(df, rsi_n=2, rsi_buy=10, sl=0.03):
    """Variant B — classic RSI-2 on daily bars. Exit when close > 5-day SMA."""
    d = df["Close"].resample("1D").last().dropna()
    o = df["Open"].resample("1D").first().dropna()
    dd = pd.DataFrame({"Close": d}).dropna()
    dd["RSI"] = rsi(dd["Close"], rsi_n)
    dd["SMA200"] = dd["Close"].rolling(200).mean()
    dd["SMA5"] = dd["Close"].rolling(5).mean()
    trades, bar_ret = [], []
    in_t = False; entry = 0.0
    vals = dd.dropna()
    for i in range(1, len(vals)):
        px = vals["Close"].iloc[i]
        if in_t:
            ret = px / entry - 1
            bar_ret.append(px / vals["Close"].iloc[i-1] - 1)
            if ret <= -sl or px > vals["SMA5"].iloc[i]:
                trades.append(ret - SLIP); in_t = False
        else:
            bar_ret.append(0.0)
            if vals["RSI"].iloc[i] < rsi_buy and px > vals["SMA200"].iloc[i]:
                in_t = True; entry = px
    return trades, bar_ret


def gauntlet(name, df, fn, ann):
    # IS = 2019-2022, OOS = 2023-2026 (true holdout)
    is_df  = df[df.index.year <= 2022]
    oos_df = df[df.index.year >= 2023]
    it, ir = fn(is_df);  ot, orr = fn(oos_df)
    im, om = metrics(it, ir, ann), metrics(ot, orr, ann)
    checks = {
        "OOS Sharpe>0.5":      om["sharpe"] > 0.5,
        "maxDD>-35%":          om["dd"] > -0.35,
        "OOS Sharpe<2.5":      om["sharpe"] < 2.5,
        "not overfit":         om["sharpe"] <= im["sharpe"] * 1.3 + 0.5,
        ">=30 trades (OOS)":   om["n"] >= 30,
        "IS Sharpe>0":         im["sharpe"] > 0,
    }
    print(f"\n{'='*64}\n{name}")
    print(f"  IS  (2019-22): n={im['n']:3d}  wr={im['wr']:.0%}  ret={im['ret']:+.1%}  "
          f"Sharpe={im['sharpe']:.2f}  DD={im['dd']:.1%}")
    print(f"  OOS (2023-26): n={om['n']:3d}  wr={om['wr']:.0%}  ret={om['ret']:+.1%}  "
          f"Sharpe={om['sharpe']:.2f}  DD={om['dd']:.1%}")
    print("  FILTERS:")
    for k, v in checks.items():
        print(f"    [{'PASS' if v else 'FAIL'}] {k}")
    verdict = all(checks.values())
    print(f"  >>> {'✅ PASSES GAUNTLET' if verdict else '❌ REJECTED'}")
    return verdict


if __name__ == "__main__":
    for sym in ["QQQ", "SPY", "IWM"]:
        try:
            df = load(sym)
        except FileNotFoundError:
            print(f"(skip {sym}: no data file)"); continue
        gauntlet(f"{sym}  A) 1h RSI(14)<30 >200EMA  [doc Prompt 1]",
                 df, backtest_intraday, ANN_H)
        gauntlet(f"{sym}  B) daily RSI(2)<10 >200SMA [classic]",
                 df, backtest_daily, ANN_D)
