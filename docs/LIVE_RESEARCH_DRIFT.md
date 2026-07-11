# LIVE vs RESEARCH DRIFT INVESTIGATION -- 2026-07-12

_Every live decision visible on this host compared against the research engine
(tools/audit_signal_parity.py + log-decision audit). VPS-side decisions need the
same battery run there; host gaps are marked, not guessed._

## Measurements

| Category | Finding | Evidence |
|---|---|---|
| **Missing signals** | Pre-fix era only: 2026-06-29 flagged MISS (2 S5 setups existed, 4 sessions evaluated, 0 signals) -- fully explained by the timezone bar-corruption bug fixed 07-05..09. Post-parity (07-10): OK (3 live signals vs 2 expected) | parity table |
| **Additional signals** | 07-10 shows 3 live S5 signals vs 2 expected -- repeated evaluation of the SAME setup across session runs. Harmless when in-position (skip guard) but becomes a REAL divergence after a same-day stop-out: research takes 1 entry/day, live can re-enter | parity table + engine code |
| **Delayed entries** | Structural: live enters mid-forming bar at :49, research at bar close. Being MEASURED per-fill via fills.csv (signal_price vs fill_price) -- data accumulating, none yet on this host | parity doc #4 |
| **Wrong exits** | Zero exit decisions logged on this host. **Measurement hole found: the fill ledger records SUBMISSIONS only -- broker-side bracket CLOSES are not captured anywhere machine-readable.** Wrong-exit detection is currently impossible without MT5 history export | grep EXIT = 0; fill_ledger fields |
| **Wrong filters** | None found post-fix: GEX/VIX/vol gates fired per spec in every logged decision line; 07-10 OK verdict. (ATR-compression "filter drift" claim separately REJECTED by review) | decision lines |
| **Wrong sizing** | **NONE.** Recomputed S5 07-10: logged shares=83.0; naive recompute 82.7 looked like drift but the logged RISK_SCALE=0.81 is display-rounded (actual throttle 0.8134 from dd=-1.493%) -> exact 83.0. Sizing chain verified end-to-end | recompute audit |
| **Wrong sessions** | This host: only dry-run subsets (by design). VPS session coverage not visible from here -- run the same battery there for MT5 truth | session grep |

## Divergences ranked by impact

1. ~~Same-day re-entry~~ **QUANTIFIED & ACCEPTED 2026-07-12** (S5_REENTRY_REVIEW: 12 extra trades/7.5y, breakeven, Sharpe delta -0.01) -- was:
   hits the highest-frequency strategy (S5), and doubles realized risk on exactly
   the worst days (stop-out days). UNQUANTIFIED -- see recommendation.
2. **Bracket closes invisible to the ledger** -- blocks wrong-exit detection AND
   month-end R/expectancy stats; MT5 history export is the workaround.
3. **Mid-bar entry approximation** -- known, bounded, being measured (fills.csv).
4. Pre-fix missing signals -- explained and fixed; no action.
5. Sizing / filters / sessions -- no drift found on available evidence.

## THE ONE recommended investigation

**Quantify the same-day re-entry divergence in replay:** run the 7-year S5 engine
twice -- (a) research mode (one entry/day) vs (b) live mode (re-enter if a new
breakout bar prints after a stop-out) -- and report: how many extra trades/year,
their win rate, and the Sharpe/DD delta. Cheap (existing engine, one flag), and it
converts the #1 unquantified divergence into a decision: if live-mode materially
degrades results, the one-entry-per-day guard justifies a post-window clock-reset
fix; if the extra entries are neutral-or-better, the divergence is documented as
acceptable and closed. Either way the drift stops being unknown.
