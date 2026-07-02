"""
prop_sim.py — Monte-Carlo a prop-firm CHALLENGE under the *exact* rules, not just
profit target + drawdown. Tests the claim that prop RULES (consistency, min-days,
daily DD) kill an edge even when it's profitable.

Models the book as a fat-tailed (Student-t) daily return stream so the consistency
rule gets a fair test (lumpy BTC-trend days are what trip it). Vol is prop-scaled.

Usage:
    python prop_sim.py                      # default FundedNext Stellar rules
    python prop_sim.py --sharpe 1.2 --vol 0.16 --consistency 0.40 --min-days 5
"""
import argparse
import numpy as np

FIRMS = {
    # target, max_dd, daily_dd, consistency(best-day cap, None=off), min_days
    "fundednext": dict(target=0.08, max_dd=0.10, daily_dd=0.05, consistency=0.40, min_days=5),
    "ftmo":       dict(target=0.10, max_dd=0.10, daily_dd=0.05, consistency=None, min_days=4),
    "the5ers":    dict(target=0.08, max_dd=0.10, daily_dd=0.05, consistency=None, min_days=3),
}


def simulate(sharpe, vol, rules, horizon_days, n_trials=40000, df=4, seed=1):
    """One challenge phase. Returns (pass_rate, fail_breakdown dict)."""
    rng = np.random.default_rng(seed)
    mu = sharpe * vol / 252
    sd = vol / np.sqrt(252)
    t_scale = sd / np.sqrt(df / (df - 2))          # scale Student-t to target sd

    p = 0
    fails = {"daily_dd": 0, "max_dd": 0, "consistency": 0, "timeout": 0}
    for _ in range(n_trials):
        eq = peak = 1.0
        start = 1.0
        best_day = 0.0            # largest single-day PROFIT (for consistency rule)
        days_traded = 0
        outcome = None
        for _ in range(horizon_days):
            r = mu + t_scale * rng.standard_t(df)
            days_traded += 1
            if r <= -rules["daily_dd"]:
                outcome = "daily_dd"; break
            day_pnl = eq * r
            eq *= (1 + r)
            if eq / peak - 1 <= -rules["max_dd"]:
                outcome = "max_dd"; break
            peak = max(peak, eq)
            best_day = max(best_day, day_pnl)
            profit = eq - start
            if profit >= rules["target"] and days_traded >= rules["min_days"]:
                # consistency: best single day must be <= X% of total profit
                if rules["consistency"] is not None and best_day > rules["consistency"] * profit:
                    continue                       # keep trading to dilute the big day
                outcome = "pass"; break
        if outcome == "pass":
            p += 1
        elif outcome is None:
            fails["timeout"] += 1
        else:
            fails[outcome] += 1
    return p / n_trials, {k: v / n_trials for k, v in fails.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firm", default="fundednext", choices=list(FIRMS))
    ap.add_argument("--sharpe", type=float, default=1.2)
    ap.add_argument("--vol", type=float, default=0.16)
    ap.add_argument("--consistency", type=float, default=None,
                    help="override best-day cap (e.g. 0.40); use -1 to disable")
    ap.add_argument("--min-days", type=int, default=None)
    args = ap.parse_args()

    rules = dict(FIRMS[args.firm])
    if args.consistency is not None:
        rules["consistency"] = None if args.consistency < 0 else args.consistency
    if args.min_days is not None:
        rules["min_days"] = args.min_days

    print(f"=== {args.firm.upper()} challenge sim — Sharpe {args.sharpe}, vol {args.vol:.0%} ===")
    print(f"rules: target +{rules['target']:.0%} | maxDD {rules['max_dd']:.0%} | "
          f"dailyDD {rules['daily_dd']:.0%} | "
          f"consistency {'off' if rules['consistency'] is None else f'best-day<{rules['consistency']:.0%}'} | "
          f"min {rules['min_days']}d\n")
    print(f"{'horizon':>10} {'PASS':>6} {'dailyDD':>8} {'maxDD':>7} {'consist':>8} {'timeout':>8}")
    for label, d in [("1 month", 21), ("2 months", 42), ("3 months", 63), ("6 months", 126)]:
        pr, f = simulate(args.sharpe, args.vol, rules, d)
        print(f"{label:>10} {pr:>6.0%} {f['daily_dd']:>8.0%} {f['max_dd']:>7.0%} "
              f"{f['consistency']:>8.0%} {f['timeout']:>8.0%}")

    # Isolate the consistency-rule cost: same book, rule on vs off
    if rules["consistency"] is not None:
        on, _ = simulate(args.sharpe, args.vol, rules, 63)
        off_rules = dict(rules); off_rules["consistency"] = None
        off, _ = simulate(args.sharpe, args.vol, off_rules, 63)
        print(f"\nConsistency-rule cost @3mo: pass {off:.0%} (off) -> {on:.0%} (on)  "
              f"= {off-on:+.0%} pts")


if __name__ == "__main__":
    main()
