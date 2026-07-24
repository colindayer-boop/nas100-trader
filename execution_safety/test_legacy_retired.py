"""Proves the legacy execution path is retired: no MT5 entry can be submitted without gate arming."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execution_safety.execution_guard import armed, arm, consume_or_block, ExecutionBlocked

def test_unarmed_blocks():
    try: consume_or_block("x"); assert False, "should have blocked"
    except ExecutionBlocked: pass

def test_armed_allows_exactly_once():
    with armed("D-123"):
        assert consume_or_block("x") == "D-123"      # first passes
        try: consume_or_block("x"); assert False, "second must block (one-shot)"
        except ExecutionBlocked: pass

def test_mt5_place_order_blocked_when_unarmed():
    import mt5_broker
    b = object.__new__(mt5_broker.MT5Broker)         # no __init__, no live connection
    try:
        b.place_order("BTC", 0.3, "buy", "BTC", sl=52000)   # the legacy BTC call shape
        assert False, "legacy place_order must be blocked"
    except Exception as e:
        assert "UNAUTHORIZED_ORDER" in str(e) or isinstance(e, ExecutionBlocked), repr(e)

if __name__ == "__main__":
    fns=[v for k,v in list(globals().items()) if k.startswith("test_")]
    p=0
    for fn in fns:
        try: fn(); p+=1; print("PASS", fn.__name__)
        except AssertionError as e: print("FAIL", fn.__name__, e)
    print(f"\n{p}/{len(fns)} legacy-retirement guarantees proven")
