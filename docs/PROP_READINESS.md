# PROP READINESS ASSESSMENT -- 2026-07-12

_Question: is the system ready for evaluation (challenge) accounts? Assessment from
existing evidence only -- no optimization, no code changes. Short answer up front:
**the DESIGN is ready; the EVIDENCE is not -- readiness date is the month-end
report (~2026-08-11), not today.**_

## Dimension-by-dimension

| Dimension | Design/backtest state | Live evidence state | Ready? |
|---|---|---|---|
| **Drawdown profile** | 3-pillar MaxDD -7.9% raw, **-4.8% with DD-throttle** (target_dd 8% under the 10% limit); throttle verified live (0.8134 computed correctly on real equity) | window day ~3: no live DD event yet | Design ✅ / Evidence ⏳ |
| **Daily loss profile** | per-trade risk 0.4-0.75%; worst plausible day (S1+S4+S5 all stopped) ~2-3% vs the 5% daily limit; kill-switch at 5% + monthly 4% guard; MC: daily-DD breach probability ~1-2%/mo at balanced sizing | no live stress day observed | Design ✅ / Evidence ⏳ |
| **Trade frequency** | ~0.8-1.6 taken/day expected (S5-dominant); satisfies min-trading-days rules easily; prop-sim says the dominant challenge failure is TIMEOUT, not blow-up -- frequency is adequate but not luxurious | 3 signals on the first clean day = on-model | Design ✅ / Evidence early |
| **Overnight exposure** | OVN (by design, 5% catastrophe stop), S3 multi-day (SL, Alpaca-only exits), BTC 24/7 (bracket+reconcile). No weekend equity holds by construction; account style matches FundedNext Stellar holding rules per PROP_PLAN | brackets held through the last VPS restart -- one good datapoint | Design ✅ |
| **Execution quality** | fill ledger + analyzer built; research assumes 3 bps/side | **ZERO measured live fills** -- slippage/spread unmeasured; and bracket CLOSES are not machine-captured (drift doc hole), so live R-multiples cannot be computed yet | ❌ NOT READY |
| **Operational reliability** | crash->Telegram excepthook, S5 watchdog, nightly HEALTHY/ACTION verdict, auto-deploy, all schtasks LastResult=0; emoji-crash class structurally fixed | ~3 clean days post-parity; the 6-day silent outage is <2 weeks in the past | Improving -- needs the month to prove MTBF |

## Remaining blockers, ranked by expected impact on a funded evaluation

1. **No clean month of live statistics** -- the gate everything else serves. A
   challenge fee bought before this exists is a bet on an unverified backtest.
   (Impact: total. Resolution: calendar -- ~2026-08-11.)
2. **Execution costs unmeasured** -- zero rows in fills.csv. If live slippage runs
   >2x the 3 bps model, every pass-probability number is wrong. (Impact: high.
   Resolution: first weeks of fills; already instrumented.)
3. **Bracket closes invisible** -- without close capture, live win-rate/R vs
   backtest cannot be computed at month-end; MT5 history export is the workaround.
   (Impact: high -- blocks the month-end comparison itself.)
4. **Same-day re-entry divergence unquantified** -- the one live-vs-research
   behavior gap that could silently change risk on stop-out days. (Impact: medium;
   investigation already specified in LIVE_RESEARCH_DRIFT.)
5. **Secrets rotation owed** -- MT5/Telegram/API credentials exposed in past chats;
   rotate before ANY real-money account. (Impact: medium-high, cheap to fix.)
6. **Single-VPS SPOF** -- brackets bound the damage but a dead host stops new
   entries and the evidence clock. (Impact: medium.)
7. **S3 on MT5 has no time exit** -- keep S3 Alpaca-only for the challenge book;
   already operationally handled via the daily age-check. (Impact: low-medium.)
8. **risk/ challenge-mode package dormant** -- challenge sizing (prop_vol_target)
   exists in config but the mode switch is unwired; manual sizing discipline
   suffices for demo, not ideal for a paid attempt. (Impact: low-medium, post-window.)

## Recommendation
Do not purchase evaluation accounts yet. The readiness decision belongs to
MONTH_1_LIVE_REPORT (~2026-08-11) with its pre-registered criteria: live results
>= ~2/3 of backtest expectation, measured slippage compatible with the cost model,
zero naked-order/crash incidents in the window. Blockers 3 and 5 should be resolved
inside the window (both are cheap and don't touch strategy surfaces); 4 is one
specified replay; 6-8 are post-window quality work. The system's job between now
and then is unchanged: accumulate honest evidence daily.
