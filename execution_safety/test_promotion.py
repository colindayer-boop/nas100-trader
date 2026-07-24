import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execution_safety.promotion_gate import can_promote
def test_incomplete_evidence_not_eligible():
    assert can_promote({})["eligible"] is False
def test_gsr_today_not_eligible():
    # GSR: internal replication only, NO shadow soak, no frozen commit, no prop sim
    gsr = dict(independent_periods=1, sharpe=1.43, ci=(0.007,0.051), after_costs=True,
               shadow_signals=0, shadow_days=0, operational_issues=0, frozen_code_commit="", prop_sim_firm="")
    r = can_promote(gsr)
    assert r["eligible"] is False
    assert any("independent periods" in f for f in r["failed_criteria"])
    assert any("shadow" in f for f in r["failed_criteria"])
def test_full_evidence_eligible():
    good = dict(independent_periods=3, sharpe=0.8, ci=(0.1,0.4), after_costs=True,
                shadow_signals=120, shadow_days=35, operational_issues=0,
                frozen_code_commit="abc123", prop_sim_firm="ftmo")
    assert can_promote(good)["eligible"] is True
if __name__=="__main__":
    fns=[v for k,v in list(globals().items()) if k.startswith("test_")]; p=0
    for fn in fns:
        try: fn(); p+=1; print("PASS",fn.__name__)
        except AssertionError as e: print("FAIL",fn.__name__,e)
    print(f"\n{p}/{len(fns)} promotion-rule guarantees proven")
