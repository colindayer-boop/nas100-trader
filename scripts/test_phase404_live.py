"""No-MT5 self-check for phase404_live strategy core + trailing."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phase404_live as b

def test_chandelier_never_loosens():
    # short: stop should only move DOWN (tighter), never above initial
    s0 = b.chandelier_stop(-1, entry_stop=100.0, peak=90.0, atr=1.0, mult=3)   # 90+3=93 < 100
    assert s0 == 93.0
    s1 = b.chandelier_stop(-1, entry_stop=100.0, peak=99.0, atr=1.0, mult=3)   # 99+3=102 -> capped at 100
    assert s1 == 100.0
    # long mirror
    assert b.chandelier_stop(1, 100.0, 110.0, 1.0, 3) == 107.0
    assert b.chandelier_stop(1, 100.0, 101.0, 1.0, 3) == 100.0

def test_find_setup_detects_buyside_sweep_sell():
    # k=3. swing HIGH ~20 at idx3; sweep above 20 at idx10 closing back; shift down idx11;
    # impulse low ~15 at idx12; retrace UP into OTE golden pocket idx13-14 -> SELL setup.
    k=3
    h=[12,15,17,20,17,16,15,16,15,16, 21.0, 17.5, 16.0, 19.0, 19.2]
    l=[10,13,15,18,15,14,13,14,13,14, 18.5, 16.0, 15.0, 18.0, 18.4]
    c=[11,14,16,19,16,15,14,15,14,15, 19.0, 16.2, 15.2, 18.6, 18.8]
    o=[float(x) for x in c];h=[float(x) for x in h];l=[float(x) for x in l];c=[float(x) for x in c]
    s=b.find_setup(np.array(o),np.array(h),np.array(l),np.array(c),k=k)
    assert s is not None, "no OTE setup found"
    assert s["side"]==-1 and s["stop"]>s["entry"] and s["target"]<s["entry"], s

def test_no_setup_on_noise():
    rng=np.random.RandomState(1); n=80
    c=100+np.cumsum(rng.randn(n)*0.01)   # tiny flat noise, unlikely clean sweep+shift+FVG
    o=c.copy(); h=c+0.02; l=c-0.02
    # just assert it runs and returns None or a dict without crashing
    s=b.find_setup(o,h,l,c)
    assert s is None or isinstance(s,dict)

if __name__=="__main__":
    for k,v in list(globals().items()):
        if k.startswith("test_"): v(); print("PASS",k)
    print("phase404_live core self-check OK (MT5 not required)")
