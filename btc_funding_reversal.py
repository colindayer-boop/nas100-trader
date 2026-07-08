"""
btc_funding_reversal.py — Funding rate extreme reversal on BTC/USDT perp.

Signal: every 8 hours Binance charges funding between longs and shorts.
  funding > +THRESH → longs are overleveraged → SHORT (they'll be forced to unwind)
  funding < -THRESH → shorts are overleveraged → LONG  (short squeeze incoming)

Why this is different from "buy the dip":
  Funding is a COST on leveraged positions. At extreme rates, even trend-followers
  voluntarily unwind because the carry cost eats their P&L. This creates a predictable
  short-term reversion in price as leveraged positions close.

Three variants tested:
  A) Pure fade: signal fires at any extreme, no trend filter
  B) With trend filter: only fade against the trend (where leverage is most one-sided)
  C) Momentum: follow the funding direction (benchmark — what if you do the OPPOSITE?)

Data: funding rate from Binance (7k+ observations, 2020–present)
      1-min BTC perp from data/btcusdt_perp_1m_{year}.parquet
OOS: IN-sample 2021–22, OUT-of-sample 2023–24
"""
import os
import warnings
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SLIP    = 0.0004   # 4bps round-trip taker fee + slippage

# ── Load data ─────────────────────────────────────────────────────────────────
def load_m1(years):
    frames = [pd.read_parquet(os.path.join(OUT_DIR, f"btcusdt_perp_1m_{y}.parquet"))
              for y in years]
    df = pd.concat(frames).sort_index()
    return df[~df.index.duplicated(keep="first")]


def load_funding():
    path = os.path.join(OUT_DIR, "btcusdt_funding.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path).squeeze()
    print("  Downloading funding rate history...")
    url, rows = "https://fapi.binance.com/fapi/v1/fundingRate", []
    start_ms = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
    s = requests.Session()
    while True:
        r = s.get(url, params={"symbol":"BTCUSDT","limit":1000,"startTime":start_ms},
                  timeout=15)
        r.raise_for_status(); data = r.json()
        if not data: break
        rows.extend(data)
        start_ms = data[-1]["fundingTime"] + 1
        if len(data) < 1000: break
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df = df.set_index("ts")["fundingRate"].astype(float)
    df.to_frame().to_parquet(path)
    return df


# ── Resample to hourly ────────────────────────────────────────────────────────
def to_hourly(m1):
    return m1.resample("1h").agg(
        Open=("Open","first"), High=("High","max"),
        Low=("Low","min"),   Close=("Close","last"),
        Volume=("Volume","sum")
    ).dropna(subset=["Open"])


# ── Backtest ──────────────────────────────────────────────────────────────────
def run(h: pd.DataFrame, funding: pd.Series,
        thresh: float, hold_h: int,
        sl: float, rr: float,
        use_trend: bool = False,
        momentum: bool = False) -> dict:
    """
    Entry: at close of the hourly bar when the 8h funding is extreme.
    Exit:  hold_h bars later OR stop/target, whichever comes first.
    use_trend: only take signals where position is AGAINST the trend
               (i.e., fade overextension while trend remains intact at 200h EMA)
    momentum:  follow the funding direction rather than fading it (control)
    """
    # Align funding to hourly bars via forward-fill
    h = h.copy()
    h["funding"] = funding.reindex(h.index, method="ffill")
    h["EMA200"]  = h["Close"].ewm(span=200, adjust=False).mean()
    h["bull"]    = h["Close"] > h["EMA200"]

    if momentum:
        # Follow: positive funding → go LONG (trend follower's view)
        long_cond  = h["funding"] >  thresh
        short_cond = h["funding"] < -thresh
    else:
        # Fade: positive funding → go SHORT
        long_cond  = h["funding"] < -thresh
        short_cond = h["funding"] >  thresh

    if use_trend:
        # Only fade when price is aligned with the overcrowded side
        # (e.g., funding > thresh AND price still near highs = bulls overcrowded)
        long_cond  = long_cond  & ~h["bull"]   # negative funding + bear = shorts overcrowded
        short_cond = short_cond &  h["bull"]   # positive funding + bull = longs overcrowded

    h["sig_long"]  = long_cond.astype(int)
    h["sig_short"] = short_cond.astype(int)

    years = sorted(h.index.year.unique())
    out = {}
    RISK = 0.007

    for Y in years:
        sub  = h[h.index.year == Y].copy()
        if len(sub) < 100: continue
        cap  = init = 10_000.0
        in_t = False
        entry = stop = tgt = 0.0; long_t = True; held = 0

        arr_sl = sub["sig_long"].to_numpy()
        arr_ss = sub["sig_short"].to_numpy()
        arr_o  = sub["Open"].to_numpy()
        arr_h  = sub["High"].to_numpy()
        arr_l  = sub["Low"].to_numpy()
        arr_c  = sub["Close"].to_numpy()

        for i in range(1, len(sub)):
            if in_t:
                held += 1
                if long_t:
                    if arr_l[i] <= stop:
                        cap += (stop - entry) / entry * cap * RISK / sl - cap * RISK * SLIP / sl
                        in_t = False
                    elif arr_h[i] >= tgt or held >= hold_h:
                        ex = tgt if arr_h[i] >= tgt else arr_c[i]
                        cap += (ex - entry) / entry * cap * RISK / sl - cap * RISK * SLIP / sl
                        in_t = False
                else:
                    if arr_h[i] >= stop:
                        cap += (entry - stop) / entry * cap * RISK / sl - cap * RISK * SLIP / sl
                        in_t = False
                    elif arr_l[i] <= tgt or held >= hold_h:
                        ex = tgt if arr_l[i] <= tgt else arr_c[i]
                        cap += (entry - ex) / entry * cap * RISK / sl - cap * RISK * SLIP / sl
                        in_t = False
            else:
                if arr_sl[i-1] == 1:
                    in_t = True; long_t = True; held = 0
                    entry = arr_c[i]; stop = entry*(1-sl); tgt = entry*(1+sl*rr)
                elif arr_ss[i-1] == 1:
                    in_t = True; long_t = False; held = 0
                    entry = arr_c[i]; stop = entry*(1+sl); tgt = entry*(1-sl*rr)

        out[Y] = (cap - init) / init
    return out


def count_signals(h, funding, thresh):
    h = h.copy()
    h["funding"] = funding.reindex(h.index, method="ffill")
    n_long  = (h["funding"] < -thresh).sum()
    n_short = (h["funding"] >  thresh).sum()
    return n_long, n_short


# ── Main ─────────────────────────────────────────────────────────────────────
YEARS = [2021, 2022, 2023, 2024]
print("Loading data...")
m1      = load_m1(YEARS)
h       = to_hourly(m1)
funding = load_funding()
print(f"  {len(h):,} hourly bars  |  {len(funding):,} funding observations")
print(f"  Funding range: {funding.min()*100:.4f}% to {funding.max()*100:.4f}% per 8h")
print(f"  Avg funding: {funding.mean()*100:.4f}%  Median: {funding.median()*100:.4f}%")

# ── Funding rate distribution ─────────────────────────────────────────────────
print(f"\n{'='*76}")
print("FUNDING RATE DISTRIBUTION (BTC/USDT perp, 2020–present)")
print(f"{'='*76}")
for pct in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    v = funding.quantile(pct/100)
    ann = v * 3 * 365
    print(f"  p{pct:>2}: {v*100:>+8.4f}%/8h  ({ann*100:>+7.1f}%/yr annualised)")

# ── Main backtest: threshold sweep ────────────────────────────────────────────
# Funding rate values from Binance are fractions: 0.0001 = 0.01%/8h
# Thresholds in same units (fractions, not percentages)
THRESHOLDS = [0.0003, 0.0005, 0.0010, 0.0020]   # = 0.03%, 0.05%, 0.10%, 0.20% per 8h
HOLD_H     = 8   # exit at next funding window
SL         = 0.020
RR         = 2.0

print(f"\n{'='*76}")
print(f"FUNDING RATE FADE — hold {HOLD_H}h, SL={SL*100:.0f}%, RR={RR:.0f}×")
print(f"{'='*76}")

hdr = f"  {'Threshold':>14}" + "".join(f"{Y:>8}" for Y in YEARS)
hdr += f"{'avg':>7}{'IN21-22':>8}{'OUT23-24':>9}{'signals':>9}"
print(hdr); print("  " + "-"*78)

results = {}
for thresh in THRESHOLDS:
    nl, ns = count_signals(h, funding, thresh)
    r    = run(h, funding, thresh, HOLD_H, SL, RR)
    avg  = np.mean([r.get(Y,0) for Y in YEARS])
    IN   = np.mean([r.get(Y,0) for Y in (2021,2022)])
    OUT  = np.mean([r.get(Y,0) for Y in (2023,2024)])
    n    = nl + ns
    row  = f"  {thresh*100:>12.3f}%/8h" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS)
    row += f"{avg:>+7.1%}{IN:>+8.1%}{OUT:>+9.1%}{n:>9,}"
    print(row)
    results[thresh] = (avg, IN, OUT, r)

# ── Trend filter variant ──────────────────────────────────────────────────────
print(f"\n{'='*76}")
print(f"WITH TREND FILTER (only fade when crowd is over-extended WITH the trend)")
print(f"{'='*76}")
print(hdr); print("  " + "-"*78)
for thresh in THRESHOLDS:
    r    = run(h, funding, thresh, HOLD_H, SL, RR, use_trend=True)
    avg  = np.mean([r.get(Y,0) for Y in YEARS])
    IN   = np.mean([r.get(Y,0) for Y in (2021,2022)])
    OUT  = np.mean([r.get(Y,0) for Y in (2023,2024)])
    row  = f"  {thresh*100:>12.3f}%/8h" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS)
    row += f"{avg:>+7.1%}{IN:>+8.1%}{OUT:>+9.1%}"
    print(row)

# ── Momentum control (follow the funding direction) ───────────────────────────
print(f"\n{'='*76}")
print(f"MOMENTUM CONTROL (follow funding direction — the OPPOSITE approach)")
print(f"{'='*76}")
print(hdr); print("  " + "-"*78)
for thresh in THRESHOLDS:
    r    = run(h, funding, thresh, HOLD_H, SL, RR, momentum=True)
    avg  = np.mean([r.get(Y,0) for Y in YEARS])
    IN   = np.mean([r.get(Y,0) for Y in (2021,2022)])
    OUT  = np.mean([r.get(Y,0) for Y in (2023,2024)])
    row  = f"  {thresh*100:>12.3f}%/8h" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS)
    row += f"{avg:>+7.1%}{IN:>+8.1%}{OUT:>+9.1%}"
    print(row)

# ── Hold period sensitivity (best threshold) ─────────────────────────────────
best_thresh = max(results, key=lambda t: results[t][0])
print(f"\n{'='*76}")
print(f"HOLD PERIOD SENSITIVITY — threshold={best_thresh*100:.2f}%/8h (best avg above)")
print(f"{'='*76}")
hdr2 = f"  {'Hold (h)':>10}" + "".join(f"{Y:>8}" for Y in YEARS) + f"{'avg':>7}"
print(hdr2); print("  " + "-"*55)
for hold_h in [1, 4, 8, 24, 48]:
    r   = run(h, funding, best_thresh, hold_h, SL, RR)
    avg = np.mean([r.get(Y,0) for Y in YEARS])
    row = f"  {hold_h:>9}h" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS) + f"{avg:>+7.1%}"
    print(row)

# ── Final verdict ─────────────────────────────────────────────────────────────
best_avg, best_IN, best_OUT, best_r = results[best_thresh]
print(f"\n{'='*76}")
print("VERDICT")
print(f"{'='*76}")
print(f"  Best threshold: {best_thresh*100:.2f}%/8h  avg={best_avg:+.1%}  IN={best_IN:+.1%}  OUT={best_OUT:+.1%}")
print()
if best_OUT > 0.03:
    print("  OUT-of-sample positive and meaningful → worth paper-trading.")
    print("  Suggested live rules:")
    print(f"    Entry:  funding crosses ±{best_thresh*100:.2f}% at 00:00/08:00/16:00 UTC")
    print(f"    Stop:   {SL*100:.0f}%  |  Target: {SL*RR*100:.0f}% ({RR:.0f}R)  |  Hard exit: {HOLD_H}h")
    print("    Size:   0.7% account risk per trade")
    print("    Broker: Bybit/Binance perp — use LIMIT orders to pay maker fee (2bps) not taker (5bps)")
elif best_OUT > 0:
    print("  OUT-of-sample weakly positive — trade very small size if at all.")
    print("  Not enough edge to be confident without more OOS data.")
else:
    print("  OUT-of-sample negative → no reliable deployable edge found.")
    print("  Funding rate fade is documented in crypto quant literature but may need")
    print("  additional filters (e.g., open interest, liquidation data) to be robust.")
print(f"{'='*76}")
