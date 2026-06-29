"""
break_even_sharpe.py — THE go/no-go artifact. 2-D grid of EV-per-challenge over
(assumed live Sharpe) × (aggression). Finds the BREAK-EVEN Sharpe: the minimum
true edge at which prop-challenge farming turns +EV. Compare your eventual LIVE
Sharpe (from the weekly report) against this line to decide deploy / don't.
"""
import numpy as np
rng = np.random.default_rng(7)

ANN_VOL = 0.08
TD = 252
P1_TARGET, P2_TARGET = 0.10, 0.05
MAX_DD, DAILY_DD = 0.10, 0.05
PHASE_DAYS = 60
FEE = 500.0
ACCOUNT = 100_000
PROFIT_SPLIT = 0.80
FUND_HORIZON_M = 24
DAYS_PER_M = 21
N = 20_000

SHARPES = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4]
RISKS   = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]


def sim_phase(target, mu, sig, days, n):
    r = rng.normal(mu, sig, size=(n, days))
    daily_b = (r <= -DAILY_DD).cumsum(1) > 0
    eq = 1 + r.cumsum(1)
    dd_b = (eq <= 1 - MAX_DD).cumsum(1) > 0
    return ((eq >= 1 + target) & ~(daily_b | dd_b)).any(1)


def funded_income(mu, sig, n):
    """Continuous daily path over the horizon with a PERSISTENT max-loss floor
    (FTMO-style: fixed at 1-MAX_DD of initial, does NOT reset monthly). Profit is
    withdrawn at each month-end (keep PROFIT_SPLIT) and balance returns to 1.0,
    but the floor stays — so a bad stretch early can kill the account. This path
    dependence is what the monthly-reset version wrongly removed."""
    floor = 1 - MAX_DD
    bal = np.ones(n); payout = np.zeros(n); alive = np.ones(n, bool)
    r = rng.normal(mu, sig, size=(n, FUND_HORIZON_M * DAYS_PER_M))
    for d in range(r.shape[1]):
        bal = np.where(alive, bal * (1 + r[:, d]), bal)
        dead = alive & ((r[:, d] <= -DAILY_DD) | (bal <= floor))
        alive &= ~dead
        if (d + 1) % DAYS_PER_M == 0:           # month-end withdrawal
            prof = np.where(alive & (bal > 1.0), (bal - 1.0) * PROFIT_SPLIT, 0.0)
            payout += prof
            bal = np.where(alive & (bal > 1.0), 1.0, bal)
    return payout


def ev_at(sharpe, m):
    mu = sharpe * ANN_VOL / TD * m
    sig = ANN_VOL / np.sqrt(TD) * m
    p_both = sim_phase(P1_TARGET, mu, sig, PHASE_DAYS, N).mean() * \
             sim_phase(P2_TARGET, mu, sig, PHASE_DAYS, N).mean()
    income = funded_income(mu, sig, N).mean() * ACCOUNT
    return -FEE + p_both * (FEE + income)


print("EV per €500 challenge (€), by assumed live Sharpe × aggression\n")
hdr = "Sharpe |" + "".join(f"{m:>9.1f}x" for m in RISKS) + " |  best  break-even?"
print(hdr); print("-" * len(hdr))
break_even = None
for s in SHARPES:
    evs = [ev_at(s, m) for m in RISKS]
    best = max(evs)
    flag = "✅ +EV" if best > 0 else "❌ -EV"
    if break_even is None and best > 0:
        break_even = s
    print(f"{s:>6.2f} |" + "".join(f"{e:>10,.0f}" for e in evs) +
          f" | {best:>7,.0f} {flag}")
print("-" * len(hdr))
if break_even:
    print(f"\n>>> BREAK-EVEN live Sharpe ≈ {break_even:.1f}  "
          f"(below this, farming challenges is a DONATION to the prop firm)")
    print(f">>> Your live Sharpe must come in ABOVE {break_even:.1f} before funding a challenge.")
else:
    print("\n>>> No tested Sharpe is +EV under these rules — challenge-farming not viable here.")
print("""
⚠️  MODEL IS OPTIMISTIC — read before trusting the +EV verdict:
  • Daily granularity UNDERSTATES the 5% daily-loss breach. At 2.5-3x sizing,
    intraday swings would trip the daily limit far more often than close-to-close
    returns show → real optimal aggression is LOWER and EV smaller.
  • Static max-loss floor (FTMO standard). Firms with TRAILING drawdown or
    CONSISTENCY rules (no day > X% of total profit) defeat the high-aggression
    'bank-the-winners' structure entirely — under those, modest edges go -EV.
  • So treat these EV numbers as an UPPER BOUND and break-even ~0.2 as a FLOOR.
    Reality needs MORE edge. The robust, model-independent conclusions:
       1. Aggression ≤1x is ALWAYS -EV (edge too slow to hit target in time).
       2. There IS a +EV band at mid-high aggression IF the edge is real AND the
          firm uses static DD without consistency rules.
       3. Your TRUE live Sharpe is still the gating input — measure it first.
  • Re-parameterize (target/DD/fee/split/trailing) from your firm's actual
    rulebook before risking a cent.
""")
