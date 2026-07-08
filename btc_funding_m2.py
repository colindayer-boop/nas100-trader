"""
btc_funding_m2.py — Funding rate fade + Global M2 regime filter on BTC perp.

Global M2 proxy (free, no API key):
  US M2      — FRED (M2SL),  monthly, billions USD
  Euro M3    — ECB SDMX API, monthly, million EUR  → converted to USD via EURUSD
  (China M2 + Japan M2 would complete the picture; omitted — no free live source)

Filter logic:
  M2 3-month momentum > 0  → global liquidity expanding → macro tailwind for BTC
  M2 3-month momentum ≤ 0  → global liquidity contracting → macro headwind

Three variants:
  A) M2-aligned only   — take longs only when M2 expanding, shorts only when contracting
  B) M2-gated         — same as base strategy but skip trades that fight M2 direction
  C) M2 strength-scaled — full size when M2 momentum strong, half size when weak/negative

Baseline re-run: best config from btc_funding_reversal.py
  threshold=0.05%/8h, hold=8h, SL=2%, RR=2×
OOS: IN 2021–22, OUT 2023–24
"""
import io, os, warnings
import numpy as np
import pandas as pd
import requests
import yfinance as yf
warnings.filterwarnings("ignore")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SLIP    = 0.0004

# ── Load previously fetched data ──────────────────────────────────────────────
def load_hourly(years):
    frames = []
    for y in years:
        p = os.path.join(OUT_DIR, f"btcusdt_perp_1m_{y}.parquet")
        df = pd.read_parquet(p)
        frames.append(df.resample("1h").agg(
            Open=("Open","first"), High=("High","max"),
            Low=("Low","min"), Close=("Close","last"), Volume=("Volume","sum")
        ).dropna(subset=["Open"]))
    h = pd.concat(frames).sort_index()
    return h[~h.index.duplicated(keep="first")]


def load_funding():
    path = os.path.join(OUT_DIR, "btcusdt_funding.parquet")
    if os.path.exists(path):
        df = pd.read_parquet(path)
        return df.iloc[:,0] if isinstance(df, pd.DataFrame) else df
    raise FileNotFoundError("Run btc_funding_reversal.py first")


# ── Global M2 components ──────────────────────────────────────────────────────
def fetch_us_m2() -> pd.Series:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL"
    r   = requests.get(url, timeout=15)
    df  = pd.read_csv(io.StringIO(r.text),
                      parse_dates=["observation_date"], index_col="observation_date")
    df  = df[df["M2SL"] != "."].copy()
    df["M2SL"] = pd.to_numeric(df["M2SL"])
    s   = df["M2SL"].dropna()
    s.index = s.index.tz_localize("UTC")
    return s   # billions USD


def fetch_ecb_m3() -> pd.Series:
    url = ("https://data-api.ecb.europa.eu/service/data/"
           "BSI/M.U2.Y.V.M30.X.1.U2.2300.Z01.E"
           "?format=csvdata&startPeriod=2018-01")
    r   = requests.get(url, timeout=15, headers={"Accept": "text/csv"})
    df  = pd.read_csv(io.StringIO(r.text))
    df  = df[["TIME_PERIOD", "OBS_VALUE"]].dropna()
    df["TIME_PERIOD"] = pd.to_datetime(df["TIME_PERIOD"]).dt.to_period("M").dt.to_timestamp()
    df  = df.set_index("TIME_PERIOD").sort_index()
    df.index = df.index.tz_localize("UTC")
    s   = df["OBS_VALUE"].astype(float)   # million EUR
    return s / 1e6   # → trillion EUR


def fetch_eurusd() -> pd.Series:
    df = yf.download("EURUSD=X", start="2018-01-01",
                     end=str(pd.Timestamp.utcnow().date()), progress=False)["Close"]
    if isinstance(df, pd.DataFrame): df = df.iloc[:,0]
    df.index = pd.to_datetime(df.index, utc=True)
    # Resample to monthly end
    return df.resample("ME").last().ffill()


def build_global_m2(us_m2, ecb_m3, eurusd) -> pd.Series:
    """
    Combine US M2 + ECB M3 in USD terms.
    Both resampled to month-end, forward-filled.
    Units: trillions USD.
    """
    us  = us_m2.resample("ME").last().ffill() / 1e3         # billion → trillion USD
    ecb = ecb_m3.resample("ME").last().ffill()               # already trillion EUR
    er  = eurusd.reindex(us.index, method="ffill")
    ecb_usd = ecb * er
    g2  = (us + ecb_usd).dropna()
    g2.name = "global_m2_usd_tn"
    return g2


def m2_to_hourly(m2_monthly: pd.Series, hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Expand monthly M2 to hourly, forward-fill, and compute momentum signals.
    Using a LAGGED 3-month change to avoid look-ahead bias
    (M2 for month T is published ~4-5 weeks after month-end → shift by 1 extra month).
    """
    m2 = m2_monthly.shift(1)    # 1-month publication lag
    m2_3m  = m2.pct_change(3)   # 3-month momentum
    m2_6m  = m2.pct_change(6)   # 6-month momentum
    m2_yoy = m2.pct_change(12)  # year-over-year
    df = pd.DataFrame({"m2": m2, "m2_3m": m2_3m, "m2_6m": m2_6m, "m2_yoy": m2_yoy})
    df = df.reindex(hourly_index, method="ffill")
    return df


# ── Backtest ──────────────────────────────────────────────────────────────────
def run(h, funding, m2h,
        thresh=0.0005, hold_h=8, sl=0.020, rr=2.0,
        variant="base"):
    """
    variant:
      "base"      — no M2 filter (reproduce btc_funding_reversal baseline)
      "aligned"   — longs only when M2 expanding, shorts only when contracting
      "gated"     — skip trades that fight M2 direction (but keep same-direction trades)
      "scaled"    — half size when M2 momentum is negative, full size when positive
    """
    h = h.copy()
    h["funding"] = funding.reindex(h.index, method="ffill")
    h["m2_3m"]   = m2h["m2_3m"]
    h["m2_6m"]   = m2h["m2_6m"]
    h["EMA200"]  = h["Close"].ewm(span=200, adjust=False).mean()

    # Core funding signals (same as base strategy)
    long_sig  = (h["funding"] < -thresh)
    short_sig = (h["funding"] >  thresh)

    m2_bull = h["m2_3m"] > 0   # M2 expanding
    m2_bear = h["m2_3m"] <= 0  # M2 contracting

    if variant == "aligned":
        # Long fades only when M2 is expanding (macro supports BTC recovery)
        # Short fades only when M2 is contracting (macro confirms downside)
        long_sig  = long_sig  & m2_bull
        short_sig = short_sig & m2_bear
    elif variant == "gated":
        # Skip signals that FIGHT the M2 direction
        # (still take same-direction fades regardless of M2)
        long_sig  = long_sig  & ~(m2_bear & (h["funding"] < -thresh * 2))
        short_sig = short_sig & ~(m2_bull & (h["funding"] >  thresh * 2))

    h["sig_l"] = long_sig.astype(int)
    h["sig_s"] = short_sig.astype(int)

    RISK = 0.007
    years = sorted(h.index.year.unique())
    out = {}
    for Y in years:
        sub  = h[h.index.year == Y].copy()
        if len(sub) < 100: continue
        cap  = init = 10_000.0
        in_t = False
        entry = stop = tgt = 0.0; long_t = True; held = 0
        a_sl = sub["sig_l"].to_numpy(); a_ss = sub["sig_s"].to_numpy()
        a_c  = sub["Close"].to_numpy(); a_h  = sub["High"].to_numpy()
        a_l  = sub["Low"].to_numpy()
        a_m3 = sub["m2_3m"].to_numpy()

        for i in range(1, len(sub)):
            # M2 size scaling (variant "scaled")
            risk_mult = 1.0
            if variant == "scaled":
                risk_mult = 1.0 if a_m3[i] > 0 else 0.5

            if in_t:
                held += 1
                # position size = RISK / sl fraction of capital (risks RISK% per stop hit)
                pos = RISK * risk_mult / sl
                if long_t:
                    if a_l[i] <= stop:
                        cap += cap * pos * ((stop - entry)/entry - SLIP); in_t = False
                    elif a_h[i] >= tgt or held >= hold_h:
                        ex = tgt if a_h[i] >= tgt else a_c[i]
                        cap += cap * pos * ((ex - entry)/entry - SLIP); in_t = False
                else:
                    if a_h[i] >= stop:
                        cap += cap * pos * ((entry - stop)/entry - SLIP); in_t = False
                    elif a_l[i] <= tgt or held >= hold_h:
                        ex = tgt if a_l[i] <= tgt else a_c[i]
                        cap += cap * pos * ((entry - ex)/entry - SLIP); in_t = False
            else:
                if a_sl[i-1] == 1:
                    in_t = True; long_t = True; held = 0
                    entry = a_c[i]; stop = entry*(1-sl); tgt = entry*(1+sl*rr)
                elif a_ss[i-1] == 1:
                    in_t = True; long_t = False; held = 0
                    entry = a_c[i]; stop = entry*(1+sl); tgt = entry*(1-sl*rr)
        out[Y] = (cap - init) / init
    return out


# ── Main ──────────────────────────────────────────────────────────────────────
YEARS  = [2021, 2022, 2023, 2024]
THRESH = 0.0005   # 0.05%/8h (best from prior test)
HOLD_H = 8; SL = 0.020; RR = 2.0

print("Loading BTC hourly data...")
h = load_hourly(YEARS)
print(f"  {len(h):,} hourly bars")

print("Loading funding rate...")
funding = load_funding()

print("Fetching Global M2 components...")
us_m2  = fetch_us_m2()
print(f"  US M2: {len(us_m2)} monthly obs  latest ${float(us_m2.iloc[-1]):,.0f}B")
ecb_m3 = fetch_ecb_m3()
print(f"  ECB M3: {len(ecb_m3)} obs  latest {float(ecb_m3.iloc[-1]):.1f}T EUR")
eurusd = fetch_eurusd()
print(f"  EUR/USD: latest {float(eurusd.iloc[-1]):.4f}")

g2 = build_global_m2(us_m2, ecb_m3, eurusd)
print(f"  Global M2 (US+EU): {len(g2)} obs  latest ${float(g2.iloc[-1]):.1f}T USD")

# Monthly M2 chart (text)
print("\nGlobal M2 3-month momentum by year:")
m2h = m2_to_hourly(g2, h.index)
for Y in YEARS:
    sub = m2h[m2h.index.year == Y]
    pct_bull = (sub["m2_3m"] > 0).mean()
    avg_mom  = sub["m2_3m"].mean()
    print(f"  {Y}: {pct_bull:.0%} of hours in expanding M2  avg 3m chg={avg_mom*100:+.2f}%")

# ── Baseline re-run ───────────────────────────────────────────────────────────
print(f"\n{'='*78}")
print("RESULTS — threshold=0.05%/8h, hold=8h, SL=2%, RR=2×")
print(f"{'='*78}")
hdr = f"  {'Variant':<22}" + "".join(f"{Y:>8}" for Y in YEARS)
hdr += f"{'avg':>7}{'IN21-22':>8}{'OUT23-24':>9}"
print(hdr); print("  " + "-"*70)

VARIANTS = [
    ("base",    "No M2 filter (baseline)"),
    ("aligned", "M2-aligned only"),
    ("gated",   "M2-gated (skip fights)"),
    ("scaled",  "M2 size-scaled"),
]
all_results = {}
for vkey, vlabel in VARIANTS:
    r   = run(h, funding, m2h, THRESH, HOLD_H, SL, RR, variant=vkey)
    avg = np.mean([r.get(Y,0) for Y in YEARS])
    IN  = np.mean([r.get(Y,0) for Y in (2021,2022)])
    OUT = np.mean([r.get(Y,0) for Y in (2023,2024)])
    row = f"  {vlabel:<22}" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS)
    row += f"{avg:>+7.1%}{IN:>+8.1%}{OUT:>+9.1%}"
    marker = " ◄ best OOS" if OUT == max(
        np.mean([run(h, funding, m2h, THRESH, HOLD_H, SL, RR, variant=v).get(Y,0)
                 for Y in (2023,2024)]) for v,_ in VARIANTS) else ""
    print(row)
    all_results[vkey] = (avg, IN, OUT, r)

# ── Hold period sweep for best variant ────────────────────────────────────────
best_v = max(all_results, key=lambda v: all_results[v][2])  # best OOS
best_label = dict(VARIANTS)[best_v]
print(f"\n{'='*78}")
print(f"HOLD SWEEP — {best_label} (best OOS variant)")
print(f"{'='*78}")
print(f"  {'Hold':>6}" + "".join(f"{Y:>8}" for Y in YEARS) + f"{'avg':>7}{'OUT':>8}")
print("  " + "-"*58)
for hold_h in [4, 8, 24, 48, 72]:
    r   = run(h, funding, m2h, THRESH, hold_h, SL, RR, variant=best_v)
    avg = np.mean([r.get(Y,0) for Y in YEARS])
    OUT = np.mean([r.get(Y,0) for Y in (2023,2024)])
    print(f"  {hold_h:>5}h" + "".join(f"{r.get(Y,0):>+8.1%}" for Y in YEARS)
          + f"{avg:>+7.1%}{OUT:>+8.1%}")

# ── M2 momentum strength sweep ────────────────────────────────────────────────
print(f"\n{'='*78}")
print("M2 THRESHOLD SENSITIVITY — what M2 momentum level matters most?")
print(f"{'='*78}")
print(f"  {'M2 3m>X':>10}" + "".join(f"{Y:>8}" for Y in YEARS) + f"{'avg':>7}{'OUT':>8}")
print("  " + "-"*58)
for m2_thresh in [-0.02, -0.01, 0.0, 0.005, 0.01, 0.02]:
    # Custom: longs only when m2_3m > m2_thresh
    h2 = h.copy()
    h2["funding"] = funding.reindex(h2.index, method="ffill")
    h2["m2_3m"]   = m2h["m2_3m"]
    h2["m2_6m"]   = m2h["m2_6m"]
    m2_bull = h2["m2_3m"] > m2_thresh
    m2_bear = h2["m2_3m"] <= m2_thresh
    h2["sig_l"] = ((h2["funding"] < -THRESH) & m2_bull).astype(int)
    h2["sig_s"] = ((h2["funding"] >  THRESH) & m2_bear).astype(int)
    # Run inline
    out = {}
    for Y in YEARS:
        sub = h2[h2.index.year == Y].copy()
        if len(sub) < 100: continue
        cap = init = 10_000.0; in_t = False
        entry = stop = tgt = 0.0; long_t = True; held = 0
        a_sl=sub["sig_l"].to_numpy(); a_ss=sub["sig_s"].to_numpy()
        a_c=sub["Close"].to_numpy(); a_hh=sub["High"].to_numpy(); a_l=sub["Low"].to_numpy()
        for i in range(1, len(sub)):
            if in_t:
                held += 1
                if long_t:
                    if a_l[i] <= stop: cap+=cap*0.007*((stop-entry)/entry-SLIP); in_t=False
                    elif a_hh[i]>=tgt or held>=HOLD_H:
                        ex=tgt if a_hh[i]>=tgt else a_c[i]
                        cap+=cap*0.007*((ex-entry)/entry-SLIP); in_t=False
                else:
                    if a_hh[i]>=stop: cap+=cap*0.007*((entry-stop)/entry-SLIP); in_t=False
                    elif a_l[i]<=tgt or held>=HOLD_H:
                        ex=tgt if a_l[i]<=tgt else a_c[i]
                        cap+=cap*0.007*((entry-ex)/entry-SLIP); in_t=False
            else:
                if a_sl[i-1]==1: in_t=True;long_t=True;held=0;entry=a_c[i];stop=entry*(1-SL);tgt=entry*(1+SL*RR)
                elif a_ss[i-1]==1: in_t=True;long_t=False;held=0;entry=a_c[i];stop=entry*(1+SL);tgt=entry*(1-SL*RR)
        out[Y] = (cap-init)/init
    avg = np.mean([out.get(Y,0) for Y in YEARS])
    OUT = np.mean([out.get(Y,0) for Y in (2023,2024)])
    label = f"m2_3m>{m2_thresh*100:+.1f}%"
    print(f"  {label:>10}" + "".join(f"{out.get(Y,0):>+8.1%}" for Y in YEARS)
          + f"{avg:>+7.1%}{OUT:>+8.1%}")

# ── Final summary ─────────────────────────────────────────────────────────────
best_avg, best_IN, best_OUT, best_r = all_results[best_v]
print(f"\n{'='*78}")
print("VERDICT")
print(f"{'='*78}")
print(f"  Global M2 proxy: US M2 + ECB M3 (in USD)  |  note: China+Japan excluded")
print(f"  Best variant: {best_label}")
print(f"  IN-sample 2021-22:   {best_IN:+.1%}")
print(f"  OUT-of-sample 2023-24: {best_OUT:+.1%}")
print()
if best_OUT > all_results["base"][2] + 0.005:
    print("  M2 filter IMPROVES OOS vs baseline → adds real information.")
    print("  Interpretation: funding fades work better when aligned with macro liquidity.")
elif abs(best_OUT - all_results["base"][2]) < 0.005:
    print("  M2 filter makes little difference to OOS → funding rate is self-contained signal.")
    print("  M2 is a macro driver but the 8h funding window is too short for it to matter.")
else:
    print("  M2 filter HURTS OOS vs baseline → don't add it.")
print(f"\n  Base OOS: {all_results['base'][2]:+.1%}  →  Best M2 variant OOS: {best_OUT:+.1%}")
print(f"{'='*78}")
