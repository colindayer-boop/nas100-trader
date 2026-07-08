"""
btc_meanrev.py — Mean-reversion backtest on BTC/USDT perpetual futures.

Data: Binance USDM futures (fapi.binance.com) — free, no API key, public endpoint.
      1-minute OHLCV bars, cached to data/btcusdt_perp_1m_{year}.parquet.
      BTC perp available from 2019-10-01.

Signal: -1 × lag_1_log_return  (same as meanrev_signal_test.py on QQQ)
Tests: hold 1/5/15/30/60 bars × cost 0/2/4/8 bps round-trip
Also sweeps signal threshold and time-of-day effects.

Run:  python btc_meanrev.py               # fetch 2020-2024, backtest
      python btc_meanrev.py --no-download  # backtest only (data already cached)
      python btc_meanrev.py --years 2022 2023 2024
"""
import argparse
import os
import time
import warnings
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SYMBOL   = "BTCUSDT"
BASE_URL = "https://fapi.binance.com"

# ── Download ──────────────────────────────────────────────────────────────────
def _ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int,
                 session: requests.Session) -> list:
    r = session.get(f"{BASE_URL}/fapi/v1/klines",
                    params={"symbol": symbol, "interval": interval,
                            "startTime": start_ms, "endTime": end_ms,
                            "limit": 1500},
                    timeout=15)
    if r.status_code == 429:
        print("  (rate limited — sleeping 10s)")
        time.sleep(10)
        return fetch_klines(symbol, interval, start_ms, end_ms, session)
    r.raise_for_status()
    return r.json()


def download_year(year: int) -> str:
    """Download 1-min BTC perp bars for the given year, save to parquet."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"btcusdt_perp_1m_{year}.parquet")
    if os.path.exists(path):
        print(f"  {year}: cached at {path}")
        return path

    start = datetime(year, 1, 1)
    end   = datetime(min(year + 1, 2026), 1, 1)
    chunk = timedelta(hours=25)   # 1500 min ÷ 60 ≈ 25h per request
    session = requests.Session()
    session.headers["User-Agent"] = "research-bot/1.0"

    frames = []
    cur = start
    req_count = 0
    while cur < end:
        nxt = min(cur + chunk, end)
        rows = fetch_klines(SYMBOL, "1m", _ms(cur), _ms(nxt) - 1, session)
        if rows:
            frames.extend(rows)
        req_count += 1
        if req_count % 100 == 0:
            pct = (cur - start) / (end - start) * 100
            print(f"    {year}: {pct:.0f}%  ({req_count} requests)", end="\r", flush=True)
        time.sleep(0.07)  # polite: ~14 req/s, well under 1200 req/min limit
        cur = nxt

    if not frames:
        print(f"  {year}: no data"); return ""

    cols = ["open_time","open","high","low","close","volume",
            "close_time","quote_vol","n_trades","taker_buy_vol","taker_buy_qvol","_"]
    df = pd.DataFrame(frames, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df = df[["open","high","low","close","volume"]]
    df.columns = ["Open","High","Low","Close","Volume"]
    df = df[~df.index.duplicated(keep="first")]
    df.to_parquet(path)
    print(f"\n  {year}: {len(df):,} bars → {path}")
    return path


def load_data(years: list) -> pd.DataFrame:
    frames = []
    for y in years:
        path = os.path.join(OUT_DIR, f"btcusdt_perp_1m_{y}.parquet")
        if not os.path.exists(path):
            print(f"  Missing {path} — run without --no-download first")
            continue
        frames.append(pd.read_parquet(path))
    if not frames:
        raise FileNotFoundError("No cached data found; run without --no-download")
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df


# ── Signal & backtest ─────────────────────────────────────────────────────────
def build_signal(df: pd.DataFrame, thresh_bps: float = 10.0) -> pd.DataFrame:
    """Add lag-1 log-return inversion signal."""
    df = df.copy()
    df["log_ret"]    = np.log(df["Close"] / df["Close"].shift(1))
    thresh           = thresh_bps / 10_000
    df["signal_raw"] = -df["log_ret"].shift(1)
    df["signal"]     = np.where(df["signal_raw"].abs() > thresh,
                                np.sign(df["signal_raw"]), 0)
    return df


def run_backtest(df: pd.DataFrame, hold_bars: int, cost_bps: float) -> dict:
    """
    Per-year returns trading the lag-1 mean-reversion signal.
    Fixed 0.5% account risk per trade; no position sizing on direction.
    Funding rate approximation: BTC perp longs pay ~0.01%/8h in bull, ignored here
    (materialises slowly; doesn't affect 1–60 bar hold results materially).
    """
    cost = cost_bps / 10_000
    years = sorted(df.index.year.unique())
    out = {}
    for Y in years:
        sub = df[df.index.year == Y]
        if len(sub) < 1000:
            continue
        cap = init = 10_000.0
        i = 0
        arr_sig   = sub["signal"].to_numpy()
        arr_close = sub["Close"].to_numpy()
        while i < len(sub):
            sig = arr_sig[i]
            if sig != 0:
                ep = arr_close[i]
                xi = min(i + hold_bars, len(sub) - 1)
                xp = arr_close[xi]
                pnl_pct = sig * ((xp - ep) / ep) - cost
                cap += cap * 0.005 * np.sign(pnl_pct) * abs(pnl_pct)
                i = xi + 1
            else:
                i += 1
        out[Y] = (cap - init) / init
    return out


def signal_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """Check if next bar moves in predicted direction (1-bar accuracy)."""
    df = df.copy()
    df["next_ret"] = np.log(df["Close"] / df["Close"].shift(1)).shift(-1)
    sig = df[df["signal"] != 0].copy()
    sig["correct"] = (sig["signal"] * sig["next_ret"]) > 0
    rows = []
    for Y, grp in sig.groupby(sig.index.year):
        rows.append(dict(
            year=Y,
            n=len(grp),
            accuracy=grp["correct"].mean(),
            avg_next_ret_bps=grp["next_ret"].abs().mean() * 10_000,
            avg_signal_bps=grp["signal_raw"].abs().mean() * 10_000,
        ))
    return pd.DataFrame(rows)


def hourly_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """1-bar accuracy by UTC hour (24/7 market — find regime pockets)."""
    df = df.copy()
    df["next_ret"] = np.log(df["Close"] / df["Close"].shift(1)).shift(-1)
    sig = df[df["signal"] != 0].copy()
    sig["correct"] = (sig["signal"] * sig["next_ret"]) > 0
    sig["hour_utc"] = sig.index.hour
    return (sig.groupby("hour_utc")
            .agg(n=("correct","count"),
                 accuracy=("correct","mean"),
                 avg_next_bps=("next_ret", lambda x: x.abs().mean() * 10_000))
            .reset_index())


# ── Main ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--no-download", action="store_true")
parser.add_argument("--years", nargs="+", type=int,
                    default=[2020, 2021, 2022, 2023, 2024])
args = parser.parse_args()

os.makedirs(OUT_DIR, exist_ok=True)

if not args.no_download:
    print(f"Downloading BTC perp 1-min data: {args.years}")
    for y in args.years:
        print(f"\n  Year {y}:")
        download_year(y)

print("\nLoading cached data...")
df = load_data(args.years)
print(f"  {len(df):,} bars  "
      f"{df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}")

# Signal stats at different thresholds
print(f"\n{'='*80}")
print("SIGNAL ACCURACY vs THRESHOLD — BTC/USDT perp 1-min")
print(f"{'='*80}")
print(f"  {'Thresh':>8}  {'N signals':>12}  {'1-bar acc':>10}  {'avg |next| bps':>14}  {'signal bps':>11}")
print(f"  {'-'*60}")
for thresh_bps in [5, 10, 20, 50, 100]:
    df_t = build_signal(df, thresh_bps)
    stats = signal_accuracy(df_t)
    n_total = stats["n"].sum()
    acc_avg = (stats["accuracy"] * stats["n"]).sum() / max(n_total, 1)
    avg_next = (stats["avg_next_ret_bps"] * stats["n"]).sum() / max(n_total, 1)
    avg_sig  = (stats["avg_signal_bps"] * stats["n"]).sum() / max(n_total, 1)
    marker = " ◄ threshold used below" if thresh_bps == 10 else ""
    print(f"  {thresh_bps:>6}bps  {n_total:>12,}  {acc_avg:>10.2%}  {avg_next:>14.2f}  {avg_sig:>11.2f}{marker}")

# Main backtest: threshold=10bps
THRESH_BPS = 10
df = build_signal(df, THRESH_BPS)
years = sorted(df.index.year.unique())

COST_CASES = [
    ("Raw (0bps)",           0.0),
    ("Perp maker (2bps)",    2.0),
    ("Perp taker (4bps)",    4.0),
    ("Retail-like (8bps)",   8.0),
]
HOLD_BARS = [1, 5, 15, 30, 60]

print(f"\n{'='*80}")
print(f"MEAN REVERSION BACKTEST — BTC/USDT perp 1-min  |  threshold={THRESH_BPS}bps")
print(f"{'='*80}")
for cost_name, cost_bps in COST_CASES:
    print(f"\n{cost_name}")
    hdr = f"  {'Hold':>6}" + "".join(f"{Y:>8}" for Y in years) + f"{'avg':>8}"
    print(hdr); print("  " + "-" * (6 + 8*len(years) + 8))
    for h in HOLD_BARS:
        r   = run_backtest(df, h, cost_bps)
        avg = np.mean(list(r.values()))
        row = f"  {h:>5}m" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in years) + f"{avg:>+8.1%}"
        print(row)

# Per-year accuracy table
print(f"\n{'='*80}")
print("1-BAR ACCURACY BY YEAR — BTC/USDT perp (threshold=10bps)")
print(f"{'='*80}")
stats = signal_accuracy(df)
print(f"  {'Year':>6}  {'N':>10}  {'1-bar acc':>10}  {'avg |next| bps':>14}  {'avg signal bps':>14}")
print(f"  {'-'*60}")
for _, row in stats.iterrows():
    marker = "  ◄ edge!" if row["accuracy"] > 0.515 else ""
    print(f"  {int(row['year']):>6}  {int(row['n']):>10,}  "
          f"{row['accuracy']:>10.2%}  "
          f"{row['avg_next_ret_bps']:>14.2f}  "
          f"{row['avg_signal_bps']:>14.2f}{marker}")

# Hour-of-day breakdown (strongest reversion windows)
print(f"\n{'='*80}")
print("HOUR-OF-DAY ACCURACY (UTC) — where mean reversion is strongest")
print(f"{'='*80}")
h_acc = hourly_accuracy(df)
top = h_acc.sort_values("accuracy", ascending=False).head(8)
bot = h_acc.sort_values("accuracy").head(4)
print("  Best hours (most mean-reverting):")
for _, row in top.iterrows():
    bar = "█" * int((row["accuracy"] - 0.48) * 400)
    print(f"    {int(row['hour_utc']):02d}:00 UTC  acc={row['accuracy']:.2%}  "
          f"n={int(row['n']):,}  avg_next={row['avg_next_bps']:.1f}bps  {bar}")
print("  Worst hours (most trending):")
for _, row in bot.iterrows():
    print(f"    {int(row['hour_utc']):02d}:00 UTC  acc={row['accuracy']:.2%}  n={int(row['n']):,}")

# Summary
print(f"\n{'='*80}")
print("KEY NUMBERS vs QQQ (for comparison)")
print(f"{'='*80}")
sig = df[df["signal"] != 0].copy()
sig["next_ret"] = np.log(df["Close"] / df["Close"].shift(1)).shift(-1)
print(f"  BTC perp 1-min:")
print(f"    Signal fires:      {len(sig):,} times / {len(df):,} bars "
      f"({len(sig)/len(df):.1%} of bars)")
print(f"    avg |next bar|:    {sig['next_ret'].abs().mean()*10000:.1f} bps")
print(f"    avg |signal|:      {sig['signal_raw'].abs().mean()*10000:.1f} bps")
print(f"    1-bar accuracy:    {(sig['signal'] * sig['next_ret'] > 0).mean():.2%}")
print(f"\n  QQQ 1-min (from meanrev_signal_test.py):")
print(f"    avg |next bar|:    6.1 bps  (threshold >5bps, n=123k)")
print(f"    1-bar accuracy:    50.5%")
print(f"\n  Breakeven cost (maker, so you earn spread not pay it):")
print(f"    If accuracy > 50% AND avg_next > 4bps → worth exploring maker execution")
print(f"    Binance perp maker fee: ~2bps  (0.02%)")
