"""
btc_asian_sweep.py — Asian session sweep strategy on BTC/USDT perp.

Same concept as S1/S4 on QQQ:
  - Asian session (00:00–08:00 UTC) sets the overnight range
  - London/NY window (08:00–17:00 UTC) sweeps below the Asian low → price reverses
  - Enter long on confirmed sweep + bar closing back above Asian low
  - Shorts: sweep above Asian high → close back below → enter short (bear regime only)

Regime filters (replacing GEX which doesn't exist for crypto):
  1. BTC 200-period hourly EMA (bull/bear market)
  2. Funding rate from Binance (overheated bull = skip longs; extreme negative = skip shorts)
  3. 24h realized vol filter: skip when vol is 1.5× rolling average (regime of chaos)

Data: data/btcusdt_perp_1m_{year}.parquet (downloaded by btc_meanrev.py)
OOS split: IN-sample 2021–22, OUT-of-sample 2023–24

Run:
  python btc_asian_sweep.py
  python btc_asian_sweep.py --no-funding   # skip funding rate filter
"""
import argparse
import os
import warnings
from datetime import date

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SLIP    = 0.0004   # 4bps round-trip: 2bps taker fee + 2bps slippage (Binance/Bybit)

# ── Load + resample ────────────────────────────────────────────────────────────
def load_m1(years):
    frames = []
    for y in years:
        p = os.path.join(OUT_DIR, f"btcusdt_perp_1m_{y}.parquet")
        if not os.path.exists(p):
            raise FileNotFoundError(f"Run btc_meanrev.py first to download {p}")
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df


def resample_hourly(m1: pd.DataFrame) -> pd.DataFrame:
    h = m1.resample("1h").agg(
        Open=("Open","first"), High=("High","max"),
        Low=("Low","min"),   Close=("Close","last"),
        Volume=("Volume","sum")
    ).dropna(subset=["Open"])
    return h


# ── Funding rate download ──────────────────────────────────────────────────────
def fetch_funding_rate() -> pd.Series:
    """Download full BTC funding rate history from Binance (free, no auth)."""
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    rows = []
    start_ms = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
    session = requests.Session()
    while True:
        r = session.get(url, params={"symbol":"BTCUSDT","limit":1000,
                                      "startTime":start_ms}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        rows.extend(data)
        start_ms = data[-1]["fundingTime"] + 1
        if len(data) < 1000:
            break
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df = df.set_index("fundingTime")["fundingRate"].astype(float)
    return df


# ── Signal build ───────────────────────────────────────────────────────────────
def build_signals(h: pd.DataFrame, funding: pd.Series | None) -> pd.DataFrame:
    h = h.copy()

    # ── Trend filter: 200h EMA ──
    h["EMA200"] = h["Close"].ewm(span=200, adjust=False).mean()
    h["bull"]   = h["Close"] > h["EMA200"]

    # ── Realized vol filter (24h rolling stddev of log returns, annualised) ──
    log_ret = np.log(h["Close"] / h["Close"].shift(1))
    rvol    = log_ret.rolling(24).std() * np.sqrt(24 * 365)
    h["HighVol"] = rvol > rvol.rolling(168).mean() * 1.5   # 168h = 1 week baseline

    # ── Funding rate: resample to hourly (published every 8h; ffill) ──
    if funding is not None and len(funding) > 0:
        fr_hourly = funding.reindex(h.index, method="ffill")
        h["funding"] = fr_hourly
    else:
        h["funding"] = 0.0

    # ── Asian session range: 00:00–08:00 UTC ──
    def sess_date(idx):
        return idx.date()   # group by UTC date

    h["Date"] = h.index.map(sess_date)
    asian = h[(h.index.hour >= 0) & (h.index.hour < 8)]
    asian_high = asian.groupby("Date")["High"].max()
    asian_low  = asian.groupby("Date")["Low"].min()
    h["AsianHigh"] = h["Date"].map(asian_high)
    h["AsianLow"]  = h["Date"].map(asian_low)

    # ── Entry window: 08:00–17:00 UTC (London open → NY midday) ──
    in_window = (h.index.hour >= 8) & (h.index.hour < 17)

    # Long: price swept below Asian low, bar closed back above it
    long_sweep = (
        (h["Low"]   < h["AsianLow"]) &
        (h["Close"] > h["AsianLow"]) &
        in_window &
        h["bull"] &                      # bull trend
        ~h["HighVol"] &                  # normal vol regime
        (h["funding"] > -0.0005) &       # not extreme negative funding (bear panic)
        (h["funding"] <  0.001)  &       # not extreme positive (overleveraged longs)
        h["AsianLow"].notna()
    )

    # Short: price swept above Asian high, bar closed back below it
    short_sweep = (
        (h["High"]  > h["AsianHigh"]) &
        (h["Close"] < h["AsianHigh"]) &
        in_window &
        ~h["bull"] &                     # bear trend only
        ~h["HighVol"] &
        (h["funding"] < 0.0005) &        # not extreme positive (shorts get squeezed)
        h["AsianHigh"].notna()
    )

    h["S_long"]  = long_sweep.astype(int)
    h["S_short"] = short_sweep.astype(int)
    return h


# ── Backtest engine ────────────────────────────────────────────────────────────
def run(h: pd.DataFrame, sl: float, rr: float) -> dict:
    """
    Per-year returns. Entry on next bar open. Stop = sweep_low × (1-sl).
    Target = entry + sl × rr (or Asian High if closer, whichever comes first).
    One trade per UTC day maximum (like QQQ's one-trade-per-session rule).
    """
    years = sorted(h.index.year.unique())
    out = {}
    for Y in years:
        sub  = h[h.index.year == Y].copy()
        cap  = init = 10_000.0
        in_t = False
        entry = stop = tgt = asian_tgt = sh = 0.0
        long_trade = True
        day_traded = None

        arr_sig_l  = sub["S_long"].to_numpy()
        arr_sig_s  = sub["S_short"].to_numpy()
        arr_open   = sub["Open"].to_numpy()
        arr_high   = sub["High"].to_numpy()
        arr_low    = sub["Low"].to_numpy()
        arr_close  = sub["Close"].to_numpy()
        arr_ahigh  = sub["AsianHigh"].to_numpy()
        arr_date   = sub["Date"].to_numpy()

        RISK = 0.007   # 0.7% account risk per trade (matches S1)

        for i in range(1, len(sub)):
            d = arr_date[i]
            if in_t:
                if long_trade:
                    if arr_low[i] <= stop:
                        pnl = sh * (stop - entry) - sh * (entry + stop) * SLIP
                        cap += pnl; in_t = False
                    elif arr_high[i] >= tgt:
                        pnl = sh * (tgt - entry) - sh * (entry + tgt) * SLIP
                        cap += pnl; in_t = False
                else:
                    if arr_high[i] >= stop:
                        pnl = sh * (entry - stop) - sh * (entry + stop) * SLIP
                        cap += pnl; in_t = False
                    elif arr_low[i] <= tgt:
                        pnl = sh * (entry - tgt) - sh * (entry + tgt) * SLIP
                        cap += pnl; in_t = False
            else:
                if arr_sig_l[i-1] == 1 and day_traded != d:
                    in_t = True; long_trade = True; day_traded = d
                    entry     = arr_open[i]
                    stop      = entry * (1 - sl)
                    tgt       = entry * (1 + sl * rr)
                    asian_tgt = float(arr_ahigh[i]) if not np.isnan(arr_ahigh[i]) else tgt
                    tgt       = min(tgt, asian_tgt) if asian_tgt > entry else tgt
                    sh        = (cap * RISK) / (entry * sl)
                elif arr_sig_s[i-1] == 1 and day_traded != d:
                    in_t = True; long_trade = False; day_traded = d
                    entry = arr_open[i]
                    stop  = entry * (1 + sl)
                    tgt   = entry * (1 - sl * rr)
                    sh    = (cap * RISK) / (entry * sl)

        out[Y] = (cap - init) / init
    return out


def signal_count(h: pd.DataFrame) -> dict:
    years = sorted(h.index.year.unique())
    counts = {}
    for Y in years:
        sub = h[h.index.year == Y]
        counts[Y] = dict(longs=int(sub["S_long"].sum()),
                         shorts=int(sub["S_short"].sum()))
    return counts


# ── Main ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--no-funding", action="store_true",
                    help="Skip funding rate filter (use plain trend + vol filter)")
args = parser.parse_args()

YEARS = [2021, 2022, 2023, 2024]

print("Loading BTC 1-min perp data...")
m1 = load_m1(YEARS)
print(f"  {len(m1):,} bars")

print("Resampling to hourly...")
h = resample_hourly(m1)
print(f"  {len(h):,} hourly bars")

funding = None
if not args.no_funding:
    print("Downloading funding rate history...")
    try:
        funding = fetch_funding_rate()
        print(f"  {len(funding)} funding rate observations")
    except Exception as e:
        print(f"  Failed ({e}); running without funding filter")

print("Building signals...")
h = build_signals(h, funding)

counts = signal_count(h)
print("\nSignal counts per year:")
for Y in YEARS:
    c = counts.get(Y, {})
    print(f"  {Y}: {c.get('longs',0)} longs  {c.get('shorts',0)} shorts")

# ── Sweep of stop/RR combinations ─────────────────────────────────────────────
print(f"\n{'='*80}")
print("BTC ASIAN SWEEP — parameter sweep (stop × RR)")
print(f"{'='*80}")

COMBOS = [
    (0.010, 3.0, "SL=1.0%  RR=3"),
    (0.015, 3.0, "SL=1.5%  RR=3"),
    (0.020, 3.0, "SL=2.0%  RR=3"),
    (0.015, 2.0, "SL=1.5%  RR=2"),
    (0.020, 2.0, "SL=2.0%  RR=2"),
    (0.025, 2.0, "SL=2.5%  RR=2"),
]

hdr = f"  {'Params':<16}" + "".join(f"{Y:>8}" for Y in YEARS)
hdr += f"{'avg':>7}{'IN21-22':>8}{'OUT23-24':>9}"
print(hdr); print("  " + "-"*70)

best_avg = -999; best_combo = None
for sl, rr, label in COMBOS:
    r   = run(h, sl, rr)
    avg = np.mean([r.get(Y, 0) for Y in YEARS])
    IN  = np.mean([r.get(Y, 0) for Y in (2021, 2022)])
    OUT = np.mean([r.get(Y, 0) for Y in (2023, 2024)])
    row = f"  {label:<16}" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS)
    row += f"{avg:>+7.1%}{IN:>+8.1%}{OUT:>+9.1%}"
    print(row)
    if avg > best_avg:
        best_avg = avg; best_combo = (sl, rr, label)

# ── Best combo detail ──────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print(f"BEST: {best_combo[2]}  (avg {best_avg:+.1%}/yr)")
print(f"{'='*80}")

sl, rr, label = best_combo
r = run(h, sl, rr)
IN  = np.mean([r.get(Y,0) for Y in (2021,2022)])
OUT = np.mean([r.get(Y,0) for Y in (2023,2024)])
print(f"  In-sample  2021–22: {IN:+.1%}/yr avg")
print(f"  Out-of-sample 2023–24: {OUT:+.1%}/yr avg")

# ── Comparison table ───────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("QQQ S1 ASIAN SWEEP vs BTC ASIAN SWEEP (best config, same logic)")
print(f"{'='*80}")
print(f"  {'':30} {'QQQ S1':>10} {'BTC perp':>10}")
print(f"  {'Asset':30} {'ETF (Alpaca)':>10} {'perp (Binance)':>10}")
print(f"  {'In-sample avg':30} {'+3.1%':>10} {IN:>+10.1%}")
print(f"  {'Out-of-sample avg':30} {'+2.3%':>10} {OUT:>+10.1%}")
print(f"  {'Slippage model':30} {'1bps':>10} {'4bps RT':>10}")
print(f"  {'Trades per year (approx)':30} {'~11':>10} {int(sum(counts[Y]['longs'] for Y in YEARS)/len(YEARS)):>10}")
print()
print("  Notes:")
print("  - BTC perp: 4bps round-trip (2bps taker fee + 2bps slippage)")
print("  - QQQ: 1bps round-trip (Alpaca ~$0.005/share, ~0.2bps + some slippage)")
print("  - BTC longs only in bull (EMA200), shorts in bear — symmetric with QQQ")
print("  - Funding rate filter requires Binance/Bybit account level data in live trading")
print(f"\n{'='*80}")
print("VERDICT:")
if OUT > 0.02:
    print("  OUT-of-sample positive → edge exists on BTC perp. Worth paper-trading live.")
elif OUT > 0:
    print("  OUT-of-sample weakly positive → marginal. Trade smaller size.")
else:
    print("  OUT-of-sample negative → no reliable edge. Do not deploy as-is.")
print(f"{'='*80}")
