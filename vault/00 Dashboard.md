# 00 Dashboard

The operating system for the nas100-trader business. Start here.

> [!info] System status
> Core prop book **execution-safe** (broker-side stops on every position).
> Edge **unconfirmed live** — clean paper-trail running. See [[10 Roadmap]].

## Map
- [[01 Trading Philosophy]] - the rules that don't change
- [[02-Strategy-Research/_index|02 Strategy Research]] - the gauntlet + graveyard
- [[03-Validated-Strategies/_index|03 Validated Strategies]] - the live book
- [[04 Risk Engine]] - sizing, throttle, kill-switch
- [[05-Broker-Integrations/_index|05 Broker Integrations]] - venues
- [[06 Execution Engine]] - orders + brackets
- [[07 Deployment]] - VPS, Actions, git
- [[08-Incidents-and-Postmortems/_index|08 Incidents]] - what broke, what we learned
- [[09 Prop Firms]] - challenge math + plan
- [[10 Roadmap]] - what's next
- [[11-Daily-Journal/_index|11 Daily Journal]]
- [[12 Ideas]] - parking lot

## Live book (Dataview)
```dataview
TABLE status, venue, exit, sharpe FROM "03-Validated-Strategies" WHERE type = "strategy" SORT key
```

## Open incidents
```dataview
TABLE date, severity, status FROM "08-Incidents-and-Postmortems" WHERE type = "incident" AND status != "resolved" SORT date DESC
```

## Recent journal
```dataview
TABLE date, summary FROM "11-Daily-Journal" WHERE type = "journal" SORT date DESC LIMIT 5
```
