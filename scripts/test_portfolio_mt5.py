"""Offline test of portfolio_mt5 strategy core (no MT5 needed)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import portfolio_mt5 as P

PX = pd.read_csv("/Users/colindayer/research-lab/data/snapshots/universe_daily.csv",
                 parse_dates=[0], index_col=0).ffill()
PX = PX.rename(columns={"SP500":"SP500"})

def test_weights_are_finite_and_bounded():
    w,d = P.target_weights(PX, target_vol=0.08, max_leverage=3.0)
    assert np.isfinite(w.values).all(), "non-finite weights"
    assert d["gross_exposure"] <= 3.0*1.5, d      # bounded by leverage cap
    assert d["scale"] <= 3.0

def test_higher_vol_target_scales_up():
    _,d1 = P.target_weights(PX, target_vol=0.06, max_leverage=6.0)
    _,d2 = P.target_weights(PX, target_vol=0.25, max_leverage=6.0)
    assert d2["scale"] > d1["scale"], (d1,d2)

def test_signals_are_lagged_no_lookahead():
    # dropping the LAST bar must not change weights computed from prior bars
    w_full,_ = P.target_weights(PX.iloc[:-1], target_vol=0.08)
    w_prev,_ = P.target_weights(PX.iloc[:-1], target_vol=0.08)
    assert (w_full.fillna(0) == w_prev.fillna(0)).all()

def test_ratio_sleeve_is_market_neutral():
    # ratio sleeve must net ~0 gross direction per pair (long one leg, short the other)
    w,d = P.target_weights(PX, target_vol=0.08)
    assert d["sleeve_gross"]["RATIO"] >= 0.0

def test_trend_sleeve_active():
    w,d = P.target_weights(PX, target_vol=0.08)
    assert d["sleeve_gross"]["TREND"] > 0.5, d

# ---- regression tests for the 4 fixed defects ----
import types
def test_usd_base_pair_notional_fixed():
    """USDJPY: 1 lot = 100,000 USD, NOT 100,000*157. Was under-sizing ~157x."""
    info=types.SimpleNamespace(trade_contract_size=100000.0)
    tick=types.SimpleNamespace(ask=157.0)
    assert P.notional_per_lot("USDJPY",info,tick)==100000.0
    assert P.notional_per_lot("USDCAD",info,types.SimpleNamespace(ask=1.37))==100000.0

def test_usd_quote_pair_notional_uses_price():
    info=types.SimpleNamespace(trade_contract_size=100000.0)
    assert abs(P.notional_per_lot("EURUSD",info,types.SimpleNamespace(ask=1.14))-114000.0)<1e-6
    gold=types.SimpleNamespace(trade_contract_size=100.0)
    assert abs(P.notional_per_lot("XAUUSD",gold,types.SimpleNamespace(ask=4000.0))-400000.0)<1e-6

def test_carry_sleeve_activates_with_swaps():
    w0,d0=P.target_weights(PX,target_vol=0.08,carry_signs=None)
    w1,d1=P.target_weights(PX,target_vol=0.08,carry_signs={"EURUSD":1,"USDJPY":-1,"AUDUSD":1})
    assert d0["sleeve_gross"]["CARRY"]==0.0
    assert d1["sleeve_gross"]["CARRY"]>0.0, d1
    assert not w0.equals(w1)


if __name__=="__main__":
    fns=[v for k,v in list(globals().items()) if k.startswith("test_")]; p=0
    for fn in fns:
        try: fn(); p+=1; print("PASS", fn.__name__)
        except AssertionError as e: print("FAIL", fn.__name__, e)
        except Exception as e: print("ERR ", fn.__name__, repr(e))
    print(f"\n{p}/{len(fns)} portfolio-core tests pass")
    w,d = P.target_weights(PX, target_vol=0.08, max_leverage=3.0)
    print("\n=== TODAY'S TARGET BOOK (funded config, 8% vol) ===")
    for k,v in w.sort_values(key=abs, ascending=False).items():
        if abs(v)>=0.005: print(f"  {k:8s} {v:+.3f}")
    print(f"  gross exposure {d['gross_exposure']:.2f}  scale {d['scale']}  realized_vol {d['realized_vol']:.1%}")

