"""
prop_ev_sim.py — Monte-Carlo EV of running prop-firm challenges, as a function of
AGGRESSION (risk multiplier). Answers: is buying challenges +EV with your edge,
and where does EV peak? Also finds the two sizings you asked about:
  • "fast-pass" bot  → risk level that maximizes P(pass) / EV per challenge
  • "no-breach" bot  → risk level that maximizes long-run funded income

KEY HONESTY: garbage in = garbage out. This assumes your edge (Sharpe/vol) is
REAL and persists live. If the edge is zero, every line below goes negative —
which is exactly the point: it tells you whether aggression is justified.

Aggression scales position size → scales BOTH daily mean and vol linearly
(Sharpe-invariant). So more risk = faster target AND faster breach.
"""
import numpy as np

rng = np.random.default_rng(7)

# ── YOUR EDGE (1x baseline) ────────────────────────────────────────────────────
ANN_SHARPE = 1.0     # honest OOS estimate of the combined stack; CHANGE to test
ANN_VOL    = 0.08    # annualized vol at 1x sizing
TD         = 252
mu_d_1x    = ANN_SHARPE * ANN_VOL / TD     # daily mean at 1x
sig_d_1x   = ANN_VOL / np.sqrt(TD)         # daily vol at 1x

# ── CHALLENGE RULES (FTMO-style 2-step; edit to your firm) ─────────────────────
P1_TARGET, P2_TARGET = 0.10, 0.05
MAX_DD      = 0.10      # static max loss from initial balance
DAILY_DD    = 0.05      # max daily loss (close vs day-start)
PHASE_DAYS  = 60        # trading days allowed per phase (FTMO now unlimited; cap for sim)
FEE         = 500.0     # challenge fee (€), refunded on first funded payout
ACCOUNT     = 100_000   # nominal (cancels out in % EV but shown for context)
PROFIT_SPLIT= 0.80
FUND_HORIZON_M = 24     # months to accrue funded payouts before stopping the count
DAYS_PER_M  = 21
N           = 40_000    # Monte-Carlo paths


def sim_phase(target, mu, sig, max_dd, daily_dd, days, n):
    """Vectorized: returns boolean pass array (reach +target before any breach)."""
    r = rng.normal(mu, sig, size=(n, days))
    daily_breach = (r <= -daily_dd).cumsum(axis=1) > 0          # ever a >5% down day
    eq = 1 + r.cumsum(axis=1)                                    # additive equity (≈ for small r)
    dd_breach = (eq <= 1 - max_dd).cumsum(axis=1) > 0           # ever down >10% from start
    reached = (eq >= 1 + target)
    # pass = reach target on some day with no prior/contemporaneous breach
    alive = ~(daily_breach | dd_breach)
    passed = (reached & alive).any(axis=1)
    return passed


def funded_income(mu, sig, max_dd, daily_dd, n):
    """Expected cumulative payout (in account-% units) over FUND_HORIZON_M months.
    Each month: trade DAYS_PER_M days; breach → account dead; else pay split*profit,
    reset to balance."""
    total = np.zeros(n); alive = np.ones(n, dtype=bool)
    for _ in range(FUND_HORIZON_M):
        r = rng.normal(mu, sig, size=(n, DAYS_PER_M))
        daily_b = (r <= -daily_dd).any(axis=1)
        eq = 1 + r.cumsum(axis=1)
        dd_b = (eq <= 1 - max_dd).any(axis=1)
        breach = daily_b | dd_b
        end = eq[:, -1]
        pay = np.where((~breach) & (end > 1), (end - 1) * PROFIT_SPLIT, 0.0)
        total += np.where(alive, pay, 0.0)
        alive &= ~breach
    return total  # fraction of account, summed


print(f"Edge assumed: Sharpe {ANN_SHARPE:.2f}, vol {ANN_VOL:.0%}/yr  (CHANGE if unrealistic)")
print(f"Challenge: P1 +{P1_TARGET:.0%} / P2 +{P2_TARGET:.0%}, maxDD {MAX_DD:.0%}, "
      f"dailyDD {DAILY_DD:.0%}, fee €{FEE:.0f}, split {PROFIT_SPLIT:.0%}\n")
print(f"{'Risk':>5} | {'P(P1)':>6} {'P(both)':>7} | {'E[payout]':>10} | "
      f"{'EV/chal €':>10} | {'EV (10 chal)':>12}")
print("-"*66)

best_ev = (-1e9, None); best_income = (-1e9, None)
for m in [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
    mu, sig = mu_d_1x * m, sig_d_1x * m
    p1 = sim_phase(P1_TARGET, mu, sig, MAX_DD, DAILY_DD, PHASE_DAYS, N).mean()
    p2 = sim_phase(P2_TARGET, mu, sig, MAX_DD, DAILY_DD, PHASE_DAYS, N).mean()
    p_both = p1 * p2
    income_frac = funded_income(mu, sig, MAX_DD, DAILY_DD, N).mean()  # %acct over horizon
    income_eur = income_frac * ACCOUNT
    # EV of one challenge: -fee, + on pass: fee refunded + funded income
    ev = -FEE + p_both * (FEE + income_eur)
    if ev > best_ev[0]: best_ev = (ev, m)
    if p_both * income_eur > best_income[0]: best_income = (p_both * income_eur, m)
    print(f"{m:>4.2f}x | {p1:>6.1%} {p_both:>7.1%} | €{income_eur:>8,.0f} | "
          f"€{ev:>8,.0f} | €{ev*10:>10,.0f}")

print("-"*66)
print(f"\n>>> EV-optimal aggression (fast-pass bot):  {best_ev[1]}x  → EV €{best_ev[0]:,.0f}/challenge")
print(f">>> Income-optimal aggression (funded bot): {best_income[1]}x  "
      f"→ €{best_income[0]:,.0f} expected over {FUND_HORIZON_M}m")
print(f"\nIf EV/challenge ≤ 0 at every risk level, the edge is too weak to farm "
      f"challenges — DON'T scale. If positive, EV×N scales (subject to your capital "
      f"for fees and the variance of small N).")
