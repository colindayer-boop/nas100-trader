# 03 Validated Strategies

The live book. Each is a validated, uncorrelated edge with a defined exit contract.

```dataview
TABLE key, status, venue, exit, stop_pct AS stop, rr, sharpe FROM "03-Validated-Strategies" WHERE type = "strategy" SORT key
```

Combined (risk-parity, corr ~0.05): **Sharpe ~1.66, -5.8% DD, +9.5%/yr** backtest.

- [[03-Validated-Strategies/S1 Asian Sweep|S1 Asian Sweep]]
- [[03-Validated-Strategies/S2 Gold FVG|S2 Gold FVG]]
- [[03-Validated-Strategies/S3 Abnormal Volume|S3 Abnormal Volume]]
- [[03-Validated-Strategies/S4 Multi Sweep|S4 Multi Sweep]]
- [[03-Validated-Strategies/S5 ORB|S5 ORB]]
- [[03-Validated-Strategies/BTC Sweep|BTC Sweep]]
- [[03-Validated-Strategies/Overnight Drift|Overnight Drift]]
- [[03-Validated-Strategies/BTC Trend|BTC Trend]]

Back: [[00 Dashboard]] | Risk: [[04 Risk Engine]] | Exec: [[06 Execution Engine]]
