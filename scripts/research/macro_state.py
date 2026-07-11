"""macro_state.py -- build/refresh the daily macro-state dataset.

One row per trading day: VIX, VIX3M, term-structure ratio, DXY, 2y/10y yields,
curve slope, HY credit spread, Fed net-liquidity proxy + canonical regime flags.
All columns are AS-OF that day's close; consumers must lag by one day for
decision-time use (a `*_lag_ok` note column documents this).

Rebuilds the full file each run (sources are tiny). Output: state/macro_daily.csv
Research/evidence only -- nothing reads this in production.

Usage: python scripts/research/macro_state.py
"""
import io
import os
import urllib.request
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "state", "macro_daily.csv")


def fred(sid):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    raw = urllib.request.urlopen(url, timeout=30).read()
    s = pd.read_csv(io.BytesIO(raw))
    s.columns = ["date", sid]
    s[sid] = pd.to_numeric(s[sid], errors="coerce")
    s["date"] = pd.to_datetime(s["date"])
    return s.set_index("date")[sid]


def yfd(t, name):
    import yfinance as yf
    s = yf.download(t, start="2018-01-01", progress=False)["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index)
    s.name = name
    return s


def main():
    vix = yfd("^VIX", "vix")
    vix3m = yfd("^VIX3M", "vix3m")
    dxy = yfd("DX-Y.NYB", "dxy")
    dgs2, dgs10 = fred("DGS2"), fred("DGS10")
    hy = fred("BAMLH0A0HYM2")
    walcl, tga, rrp = fred("WALCL"), fred("WTREGEN"), fred("RRPONTSYD")

    df = pd.concat([vix, vix3m, dxy], axis=1)
    df["dgs2"] = dgs2.reindex(df.index, method="ffill")
    df["dgs10"] = dgs10.reindex(df.index, method="ffill")
    df["hy_oas"] = hy.reindex(df.index, method="ffill")
    netliq = (walcl - tga.reindex(walcl.index, method="ffill")
              - rrp.reindex(walcl.index, method="ffill"))
    df["netliq_bn"] = netliq.reindex(df.index, method="ffill")

    # derived
    df["ts_ratio"] = df["vix3m"] / df["vix"]
    df["vix21ma"] = df["vix"].rolling(21).mean()
    df["curve_10y2y"] = df["dgs10"] - df["dgs2"]
    df["dxy_200ma"] = df["dxy"].rolling(200).mean()
    df["hy_200ma"] = df["hy_oas"].rolling(200).mean()
    # canonical regime flags (same rules as the Part B segmentation -- NOT optimized)
    df["flag_vix_calm"] = (df["vix21ma"] < 20).astype(int)
    df["flag_contango"] = (df["ts_ratio"] > 1.0).astype(int)
    df["flag_curve_pos"] = (df["curve_10y2y"] > 0).astype(int)
    df["flag_hy_calm"] = (df["hy_oas"] < df["hy_200ma"]).astype(int)
    df["flag_dxy_weak"] = (df["dxy"] < df["dxy_200ma"]).astype(int)
    df["flag_dgs2_falling"] = (df["dgs2"].diff(63) < 0).astype(int)
    df["flag_netliq_rising"] = (df["netliq_bn"].diff(13) > 0).astype(int)

    df = df.dropna(subset=["vix", "vix3m"]).round(4)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index_label="date")
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(df)} rows, "
          f"{df.index.min().date()} -> {df.index.max().date()}, {len(df.columns)} cols")
    # self-check (ponytail: smallest thing that fails if the logic breaks)
    last = df.iloc[-1]
    assert 5 < last["vix"] < 100 and 0.5 < last["ts_ratio"] < 2.0, "sanity bounds"
    assert set(df["flag_contango"].unique()) <= {0, 1}
    print("self-check OK | latest:", df.index.max().date(),
          f"vix={last['vix']:.1f} ts_ratio={last['ts_ratio']:.3f} "
          f"contango={int(last['flag_contango'])}")


if __name__ == "__main__":
    main()
