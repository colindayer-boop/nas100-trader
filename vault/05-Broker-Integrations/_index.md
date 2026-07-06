# 05 Broker Integrations

Venue adapters implement one ABC: `get_bars, get_account, get_positions,
place_order(sl,tp), close_position`.

```dataview
TABLE brackets, status, use FROM "05-Broker-Integrations" WHERE type = "broker" SORT status
```

- [[05-Broker-Integrations/MT5 Pepperstone|MT5 / Pepperstone]]
- [[05-Broker-Integrations/Alpaca|Alpaca]]
- [[05-Broker-Integrations/Others|Binance / cTrader / Tradovate]]

Back: [[00 Dashboard]] | [[06 Execution Engine]]
