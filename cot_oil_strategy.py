"""
cot_oil_strategy.py — COT hedging-pressure signal → real long/flat oil strategy,
full gauntlet. Signal: commercial hedgers (producers/banks) in the TOP quintile of
their trailing 3yr net positioning = bullish (they hedge/accumulate at bottoms).
Go LONG oil that week, else FLAT. Costs on. IS/OOS split. Correlation vs QQQ.
"""
import urllib.request, urllib.parse, json, pandas as pd, numpy as np
import yfinance as yf, warnings; warnings.filterwarnings("ignore")
from datetime import date

COST = 0.0015            # round-trip oil (ETF/futures spread+commission), per position change
THRESH = 0.80            # "extreme long" = top quintile of 3yr commercial positioning
BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"


def fetch_cot(code):
    rows = []; off = 0
    while True:
        q = {"$limit": "10000", "$offset": str(off),
             "$where": f"cftc_contract_market_code='{code}'",
             "$select": "report_date_as_yyyy_mm_dd,comm_positions_long_all,comm_positions_short_all,open_interest_all"}
        url = BASE + "?" + urllib.parse.urlencode(q)
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "r"}), timeout=60).read())
        if not d: break
        rows += d; off += len(d)
        if len(d) < 10000: break
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
    for c in ["comm_positions_long_all", "comm_positions_short_all", "open_interest_all"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("date").drop_duplicates("date")
    df["comm_net"] = (df["comm_positions_long_all"] - df["comm_positions_short_all"]) / df["open_interest_all"]
    return df.set_index("date")["comm_net"]


cot = fetch_cot("067651")          # WTI crude
print(f"COT crude: {len(cot)} weeks {cot.index.min().date()} -> {cot.index.max().date()}")
cot_index = cot.rolling(156, min_periods=52).apply(lambda x: (x.iloc[-1] > x).mean())

# weekly oil price (CL=F signal instrument) + QQQ for correlation
oil = yf.download("CL=F", start="1999-01-01", end=str(date.today()), progress=False, auto_adjust=True)["Close"]
qqq = yf.download("QQQ", start="1999-01-01", end=str(date.today()), progress=False, auto_adjust=True)["Close"]
if isinstance(oil, pd.DataFrame): oil = oil.iloc[:, 0]
if isinstance(qqq, pd.DataFrame): qqq = qqq.iloc[:, 0]
oilw = oil.resample("W-FRI").last(); qqqw = qqq.resample("W-FRI").last()
oilret = oilw.pct_change(); qqqret = qqqw.pct_change()

sig = (cot_index > THRESH).astype(int).reindex(oilw.index, method="ffill").fillna(0)
pos = sig.shift(1).fillna(0)                       # act on prior week's signal (no lookahead)
turn = pos.diff().abs().fillna(0)
strat = pos * oilret - turn * COST
strat = strat.dropna()


def block(lo, hi):
    s = strat[(strat.index.year >= lo) & (strat.index.year <= hi)]
    p = pos.reindex(s.index)
    active = s[p == 1]
    if len(active) < 5: return None
    eq = (1 + s).cumprod()
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    entries = int(((p.diff() == 1)).sum())
    return dict(weeks_long=int((p == 1).sum()), trades=entries, wr=(active > 0).mean(),
                cagr=eq.iloc[-1]**(1/yrs)-1 if yrs > 0 else 0, ret=eq.iloc[-1]-1,
                sharpe=s.mean()/s.std()*np.sqrt(52) if s.std() > 0 else 0,
                dd=(eq/eq.cummax()-1).min())


IS, OOS = block(2000, 2013), block(2014, 2026)
print(f"\nStrategy: LONG WTI when commercials in top {1-THRESH:.0%} of 3yr positioning, else FLAT")
for lab, m in [("IS  2000-13", IS), ("OOS 2014-26", OOS)]:
    print(f"  {lab}: trades={m['trades']} wks_long={m['weeks_long']} win={m['wr']:.0%} "
          f"CAGR={m['cagr']:+.1%} Sharpe={m['sharpe']:.2f} maxDD={m['dd']:.0%}")
# buy-hold oil reference (OOS)
bh = (1+oilret[(oilret.index.year>=2014)]).cumprod()
print(f"  (WTI buy-hold OOS: ret={bh.iloc[-1]-1:+.0%})")

# correlation to equity book (QQQ proxy), full period, active weeks
both = pd.DataFrame({"oil": strat, "qqq": qqqret}).dropna()
corr = both["oil"].corr(both["qqq"])

checks = {
    "OOS Sharpe>0.5": OOS["sharpe"] > 0.5, "maxDD>-35%": OOS["dd"] > -0.35,
    "OOS Sharpe<2.5": OOS["sharpe"] < 2.5,
    "not overfit": OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
    ">=30 trades": OOS["trades"] >= 30, "IS Sharpe>0": IS["sharpe"] > 0,
}
print("\n  GAUNTLET:")
for k, v in checks.items(): print(f"    [{'PASS' if v else 'FAIL'}] {k}")
print(f"    [{'PASS' if abs(corr) < 0.3 else 'FAIL'}] low corr to equity book (QQQ): {corr:+.2f}")
print(f"\n  >>> {'PASSES — real uncorrelated edge' if all(checks.values()) and abs(corr)<0.3 else 'see filters'}")
