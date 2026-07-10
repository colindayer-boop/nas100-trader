# TENSORTRADE EVALUATION — should it join the Research OS?

_Empirical evaluation, 2026-07-10. Everything below was tested in an isolated
scratchpad venv; zero production code touched, nothing installed into the repo
environment. **Recommendation up front: DEFER — do not adopt now** (details in §7)._

## 1. Installation (isolated env) — WORKS, but only with surgery

Tested: `tensortrade 1.0.4` (released 2026-02-06 — the project IS maintained),
`requires_python >= 3.12`, in a dedicated venv on Python 3.13.9.

A clean `pip install tensortrade` **fails** on Python 3.13. Root causes, verified:
- dependency `stochastic 0.6.0` pins `numpy<2.0`, and numpy 1.x has no
  cp313 wheels → `ResolutionImpossible` (works cleanly only on Python 3.12);
- dependency `ta` ships source-only (no wheel);
- `pandas<3.0` pin conflicts with our tooling (repo uses pandas 3.0.3).

Working recipe (what I actually ran):
```
python3 -m venv tt_env && tt_env/bin/pip install -U pip
tt_env/bin/pip install numpy pandas scipy gymnasium pyyaml matplotlib tensorflow
tt_env/bin/pip install ta stochastic deprecated ipython
tt_env/bin/pip install "pandas>=2.2.3,<3.0"      # TT's pin
tt_env/bin/pip install --no-deps tensortrade
```

## 2. Verification — smoke test PASSED

```
tensortrade 1.0.4 | Python 3.13.9 | env constructed OK
random policy: 100 steps | cum reward 168426902.17 | net worth 1182.95 (from 1000)
SMOKE TEST PASS
```
Exercised: `Exchange` + simulated execution, `Portfolio`/`Wallet` OMS, `DataFeed`
streams, `managed-risk` action scheme, `risk-adjusted` reward scheme, gymnasium
`reset/step` loop. One API footgun found: `Stream.rename()` mutates in place —
the exchange price stream and the observer feed need **separate** stream objects.

**Compatibility verdict:** usable in an isolated venv only. Its `pandas<3` pin
means it can never share an environment with our tooling — which is fine, because
research isolation is our rule anyway.

## 3. How it could integrate with the Research OS

TensorTrade is an **RL environment framework** (gymnasium-compatible market sim +
portfolio accounting + reward shaping). It is not a backtester replacement and
not a signal library. The only sane mount point:

```
research/experiments/EXP-...-rl-<name>/
    env_config.py      # TT env built from OUR data (qqq_hourly_7y.csv etc.)
    train.py           # runs in the tt_env venv, never the repo env
    result.json        # standard experiment schema (ROADMAP_V2 #2)
    trades.csv         # THE bridge artifact: the policy's trade list
```

## 4. Output flows into the existing systems

| TT output | Flows to | How |
|---|---|---|
| trained policy checkpoint | `research/experiments/EXP-*/artifacts/` | opaque blob; archived, never deployed |
| **episode trade list (trades.csv)** | **experiment pipeline** | the ONLY first-class output: scored by the gauntlet exactly like any strategy's trade series (IS/OOS, costs, corr, 6/6 splits) |
| training metrics (reward curves) | Obsidian via the bridge | AUTO-block section in the EXP note; charts as linked images |
| run report | research dashboard | via `result.json` -> `experiments.json` (ROADMAP_V2 #3/#6) |

The trade list is the key design decision: **a policy is judged only by the
trades it would have taken, on held-out data, through the same gauntlet as every
human idea.** Reward curves prove nothing (they are in-sample by construction).

## 5. Safe integration design — hypothesis generator, never a trader

1. **Environment firewall:** TT lives in its own venv; nothing in the repo env
   imports it; `live_trader.py`/brokers never see it. (Enforced naturally by the
   pandas-3 conflict — it *cannot* be imported in the production env.)
2. **No execution path:** only TT's *simulated* exchange is ever used. No broker
   adapter is ever written for it. Its OMS is a training fiction.
3. **Output contract:** the only thing that leaves the sandbox is `trades.csv` +
   `result.json`. Policies are artifacts, not deployables.
4. **Pipeline gates unchanged:** EXP note -> queue -> running -> gauntlet ->
   reviewer (different model) -> human. RL gets zero shortcuts.
5. **Anti-overfit escalation:** an RL policy is a *massive* searched hypothesis
   space — the 6/6 split-robustness bar applies to the POLICY'S OOS trade list,
   and the note must record the number of training runs attempted (a 1-in-20
   cherry-picked policy is the EWA/EWC trap at industrial scale).

## 6. Comparison with the existing pipeline

| | paper→idea→experiment (current) | TensorTrade RL |
|---|---|---|
| hypothesis source | human/AI reading + mechanism reasoning | gradient descent over reward |
| explainability | full (rules are the strategy) | near zero (policy is a network) |
| overfit risk | contained by a-priori params | extreme by construction |
| validation | gauntlet (works as-is) | gauntlet on exported trade list (works, needs export shim) |
| infra cost | none new | separate venv (or py3.12), TF ~0.5-1GB, GPU-hungry training, dep drift |
| maps to prop trading | directly (CFD rules, stops) | poorly (policies don't emit stop/target brackets natively — bracket-compatibility itself is a research question) |

The pipeline doesn't need TT to function; TT would be one more *experiment type*
inside it. Nothing in the current workflow is duplicated by TT except its
simulator, which our backtest engines already cover more faithfully (real costs,
our instruments, our session structure).

## 7. Recommendation — DEFER (do not adopt now)

**Unique value:** yes, one thing — a maintained gymnasium market environment
with portfolio accounting, if we ever want to test RL-generated hypotheses.
Nothing else it offers is missing from the stack.

**Why not now:**
1. **Philosophy collision:** the project's hardest-won lesson is that searched
   hypothesis spaces produce split-luck (EWA/EWC, SSRN momentum). RL is that
   failure mode industrialized. Our gauntlet can contain it, but the expected
   value of RL-on-price-bars for a book of sparse, mechanism-driven edges is low.
2. **The book doesn't need it:** the binding constraint is the 30-day live
   window, not hypothesis supply. The graveyard shows supply was never the issue.
3. **Real maintenance cost:** py3.12-or-surgery installs, pandas<3 world,
   TF-sized dependency, API footguns — a standing tax on every future session.
4. **Prop mismatch:** policies don't naturally emit broker-side SL/TP brackets —
   the one thing every live order here must carry.

**If adopted later** (post-window, only if a specific RL hypothesis earns a
queue slot): follow §5 exactly — isolated venv, trades.csv contract, gauntlet
on OOS trade lists, training-run count disclosed, reviewer + human gates.
File it as `research/ideas/` first, like everything else.

**Bottom line:** technically viable (proven above), philosophically expensive,
strategically unnecessary today. The evaluation cost one venv; adopting it would
cost a standing slice of every research session. Defer.
