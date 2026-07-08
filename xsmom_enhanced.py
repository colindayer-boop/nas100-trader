def spy_bench(lo, hi):
    """Buy‑and‑hold SPY stats for the same period."""
    spy = monthly_closes(["SPY"])["SPY"].pct_change().dropna()
    spy = spy[(spy.index.year >= lo) & (spy.index.year <= hi)]
    eq = (1 + spy).cumprod()
    # Ensure scalar values
    cagr_val = float(eq.iloc[-1].item())
    sharpe_val = float((spy.mean()/spy.std()*np.sqrt(12)).item())
    dd_val = float((eq/eq.cummax()-1).min().item())
    return dict(cagr=cagr_val, sharpe=sharpe_val, dd=dd_val)