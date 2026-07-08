# CTO‑Level Architecture Review – nas100‑trader

## 1. Architectural Strengths
| Strength | Why it matters | Evidence in codebase |
|----------|----------------|----------------------|
| **Broker Abstraction Layer** | Decouples strategy logic from broker‑specific APIs, enabling multi‑broker deployment (Alpaca, Tradovate, cTrader, Binance, MT5) and easy dry‑run/testing. | `broker.py` defines abstract `Broker`; each adapter implements the same interface; `live_trader.py` calls only these methods. |
| **Stateless Strategy Functions** | Each session/run is a pure function of the current market data and optional persistent state files; facilitates horizontal scaling and easy restart/recovery. | All `run_*` functions receive `broker`, `equity`, `open_syms`, regime flags, etc., and return after placing/canceling orders. |
| **Centralized Risk & Position‑Sizing Rules** | Single source of truth for risk parameters (`RISK_S*`, `STOP_*`, `RR_*`, daily/monthly kill‑switches, conformal DD‑throttle) reduces drift and bugs. | Defined at top of `live_trader.py`; `update_risk_state()` applies the throttle globally. |
| **Explicit State Persistence** | Strategies that need to hold positions across invocations (BTC sweep, overnight drift, BTC trend, monthly rebalance) use tiny JSON files; this makes the system resilient to process restarts and simplifies debugging. | Files like `logs/btc_state.json`, `logs/ovn_state.json`, etc. |
| **Clear Execution Schedule (Cron‑style) Documentation** | The `RUN.md` file documents exactly when each strategy subset runs, making deployment and monitoring predictable. | `RUN.md` table with UTC times and corresponding `--session` flags. |
| **Logging & Alerting Hook** | Central logger + simple `alerts.py` wrapper gives observability without tying the core to a specific notification service. | Logging configured in `live_trader.py`; `alerts.send()` used throughout. |
| **Modular Strategy Implementation** | Each strategy lives in its own clearly named function (`run_s1`, `run_s2`, …) making it easy to locate, test, or replace a single logic block. | Functions are ~50‑150 lines each, well‑commented. |
| **Dependency Isolation via Requirements** | `requirements.txt` pins only core libraries (pandas, numpy, alpaca-py, requests, etc.) keeping the runtime lightweight and reproducible. | Present in repo root. |

## 2. Areas of Excessive Coupling
| Coupling Issue | Impact | Location |
|----------------|--------|----------|
| **Global Regime Flags Shared Across Strategies** | The `vix_ma21`, `spy_bull`, `vix_mult`, `qqq_bear200` variables are computed once in `live_trader.py` and passed down to every strategy function. While this avoids recomputation, it forces every strategy to accept these four arguments even if they don’t need all of them, creating a fragile interface. Adding a new regime metric requires changing the signature of *all* `run_*` functions. | Function signatures of `run_s1…run_s5`, `run_sweep_basket`, etc.; call sites in the main dispatcher. |
| **Hard‑coded Symbol Lists in Strategy Functions** | Lists like `SYMBOLS = ["QQQ", "GLD", "GDX", "SLV", "USO"]` in `run_s3` and the sweep basket list in `run_sweep_basket` are duplicated logic; if the universe evolves, changes must be made in multiple places. | `run_s3()` (lines 366‑…); `run_sweep_basket()` (lines 782‑…); also the `XSMOM_UNIVERSE` constant in `run_xsmom`. |
| **Direct Access to Broker‑Specific Attributes** | Some strategies reference `broker.RISK_SCALE` directly (e.g., when computing shares). While this is part of the broker interface, it couples the strategy to the broker’s internal risk‑scaling mechanism; a broker that doesn’t expose such an attribute would break the strategy. | Several places where `equity * RISK_S* * vix_mult * broker.RISK_SCALE` is used (e.g., line 287, 349, 484, 535, 540, 613, 759). |
| **State‑File Paths Hard‑coded** | Paths like `logs/btc_state.json` are built using string concatenation inside each strategy. Changing the log directory location would require edits in many functions. | `_btc_state_path`, `_ovn_state_path`, `_btctrend_state` definitions near the respective strategy functions. |
| **Tight Coupling to `yfinance` for Regime/GEX** | `get_regime()` and `get_gex_levels()` directly call `yfinance.download`. If the data source changes (e.g., to a paid provider or a custom CSV feed), every part of the system that calls them must be updated. | Lines 142‑163 (`get_regime`) and 165‑213 (`get_gex_levels`). |

## 3. Potential Bottlenecks
| Component | Reason it could become a bottleneck | Mitigation |
|-----------|--------------------------------------|------------|
| **Broker API Rate Limits** (especially Alpaca and Binance) | All strategies call `get_bars` for their symbols each run; during high‑frequency sessions (e.g., hourly BTC sweep) many parallel requests may hit rate limits, causing delays or errors. | Implement a shared data‑cache layer (e.g., in‑memory TTL cache or Redis) that serves recent bars to all strategies; batch requests where possible. |
| **Serial Execution of Strategies within a Session** | In the `all` and `sweep` sessions, strategies are invoked sequentially (`run_s1`, `run_s2`, `run_s4`, `run_s5`, `run_s3`, `run_sweep_basket`). If one strategy’s data fetch or order placement is slow, it delays the rest, potentially causing missed windows (e.g., ORB window 10‑13 ET). | Run strategies concurrently (thread‑pool or async) where they are independent, synchronizing only on shared resources like the risk state file. |
| **Single Point of Failure for Risk State File** | `update_risk_state()` reads/writes a JSON file per broker. Under heavy concurrent access (multiple instances or threads) there is a risk of race conditions leading to incorrect `RISK_SCALE`. | Use file‑based locking (e.g., `portalocker`) or migrate the risk state to a lightweight SQLite database or in‑memory store with atomic updates. |
| **YFinance Downloads for Regime/GEX** | These calls are made every time the trader runs (potentially every few minutes). Yahoo Finance may throttle or temporarily block the IP, causing missing regime data and causing strategies to fallback to default behavior (e.g., pausing due to VIX multiplier = 0). | Cache the regime/GEX results for a short window (e.g., 5‑15 minutes) or switch to a more resilient data source (e.g., a self‑hosted Redis cache of pre‑computed VIX/SPY/QQQ values). |
| **Order Execution Serialization via `place_order_safe`** | While the retry loop is good for reliability, it is synchronous; if the broker’s API is slow, each order blocks the next. This can become noticeable when sending many orders (e.g., sweep‑basket with up to 9 symbols). | Use asynchronous order submission (if broker SDK supports it) or a thread‑pool to send orders in parallel, while still preserving idempotency and duplicate‑order protection via client order IDs. |

## 4. Vision for the Architecture in 2 Years
> **Goal:** A horizontally scalable, observable, and maintainable trading platform that can run dozens of strategies across multiple asset classes and brokers with minimal manual intervention.

### High‑Level Blueprint
```
+-------------------+       +-------------------+       +-------------------+
|   Config / Secrets|       |   Market Data Hub |       |   Runtime Scheduler|
| (YAML/Vault)      |<----->| (Cache + WebSocket|<----->|   (Cron/K8s CronJob)|
+-------------------+       |   + Indicators)   |       +-------------------+
        ^                         ^                         ^
        |                         |                         |
        |                         |                         |
+-------------------+       +-------------------+       +-------------------+
|   Strategy Service|<----->|   Risk & Position |<----->|   Broker Adapter  |
|   (Plug‑in)       |       |   Service         |       |   (Plug‑per‑Broker)|
+-------------------+       +-------------------+       +-------------------+
        ^                         ^                         ^
        |                         |                         |
        |                         |                         |
+-------------------+       +-------------------+       +-------------------+
|   Order Executer  |       |   State Store     |       |   Observability   |
|   (Idempotent)    |<----->|   (Redis/Postgres)|<----->|   (Logging, Metrics,
+-------------------+       +-------------------+       |    Alerts, Tracing)|
                                                         +-------------------+
```

### Key Changes from Current Architecture
1. **Market Data Hub** – Instead of each strategy calling `yfinance` or broker REST endpoints individually, a centralized service subscribes to WebSocket streams (or polls a reliable vendor) and caches OHLCV, VIX, GEX, and derived indicators. Strategies read from an in‑memory store or a lightweight pub/sub (Redis Streams, Apache Pulsar). This eliminates duplicate HTTP calls and provides low‑latency, consistent data.
2. **Strategy Service / Plugin Architecture** – Each strategy becomes an independent deployable unit (Docker container or WASM plugin) that implements a simple interface: `on_market_tick(data) -> OrderIntent`. The service plugs into a orchestrator which handles scheduling, concurrency, and risk limits. This enables:
   * Independent versioning and rollout.
   * Language flexibility (e.g., Python for research, Rust/C++ for latency‑critical strategies).
   * Easy A/B testing of strategy variants.
3. **Risk & Position Service** – Centralized authority that receives proposed orders, validates against per‑strategy limits, global drawdown, max position, and concurrency limits, then emits a final order or rejection. It also maintains the dynamic DD‑throttle and kill‑switch state in a fault‑tolerant store (Redis with persistence or PostgreSQL).
4. **Broker Adapter Layer (Pluggable)** – Rather than having each strategy know about a specific broker, a thin adapter translates generic `OrderIntent` (symbol, side, qty, order type) into broker‑specific calls. New brokers can be added by implementing the adapter interface without touching strategy code.
5. **State Store** – Long‑lived strategy state (e.g., BTC sweep entry price, open positions for overnight drift) lives in a shared, replicated store (Redis Hashes or a timeseries DB). This removes the need for per‑strategy JSON files and allows multiple instances to share state safely.
6. **Observability Stack** – Structured logging (JSON), Prometheus metrics (trade latency, order fill rate, risk‑scale, strategy PnL), and distributed tracing (OpenTelemetry) to quickly identify bottlenecks or anomalies.
7. **Orchestration / Scheduling** – Replace ad‑hoc cron scripts with a Kubernetes CronJob or a lightweight scheduler (e.g., Airflow, Prefect) that can launch strategy containers at the desired UTC times, scale them horizontally, and enforce resource quotas.
8. **Deployment & CI/CD** – GitOps workflow: Docker images built on push to `main`, Helm charts for Kubernetes, automated testing (unit and integration tests with mock broker), and canary releases.

### Expected Benefits
* **Scalability** – Hundreds of strategy instances can run concurrently; adding a new instrument or broker does not increase per‑strategy load.
* **Resilience** – Failure of one strategy or broker does not bring down the whole system; circuit‑breaker patterns in the risk service halt faulty order flow.
* **Observability** – Real‑time dashboards show per‑strategy Sharpe, win‑rate per strategy, latency, order‑reject reasons; alerts fire on risk‑limit breaches.
* **Development Speed** – Researchers can prototype a new strategy in isolation, test against historical data via the market‑data‑hub replay mode, and promote to production with a single PR.
* **Cost Efficiency** – Cloud‑native autoscaling reduces idle compute; spot instances can be used for batch‑oriented strategies (e.g., monthly rebalance).  

## 5. Principles That Should Never Change
| Principle | Reason |
|-----------|--------|
| **Clear Separation of Concerns** (Strategy ↔ Risk ↔ Data ↔ Execution) | Guarantees that changes in one domain (e.g., adding a new broker) never unintentionally alter trading logic. |
| **Deterministic, Auditable Order Flow** – Every order must be traceable from signal generation → risk check → broker acknowledgment. | Essential for compliance, post‑trade analysis, and debugging; any deviation introduces hidden risk. |
| **Risk‑First Mindset** – Position sizing, stop‑loss, daily/monthly caps, and the conformal DD‑throttle are *gatekeepers* that must execute before any market interaction. | Protects capital; removing or weakening them has historically led to blow‑ups. |
| **Idempotent Order Submission** – Using client‑order‑ids and checking existing state before sending a new order prevents duplicate fills. | Guarantes exactly‑once semantics even under retries or process restarts. |
| **Explicit, Version‑Controlled Configuration** – All parameters (risk thresholds, symbol lists, scheduler cron expressions) live in version‑controlled files (YAML/JSON) or a secure vault. | Guarantees reproducibility and enables rollback to a known‑good state. |
| **Minimal External Side Effects in Core Logic** – The core strategy functions should not directly mutate global state or perform I/O (except via well‑defined interfaces). | Makes unit testing straightforward and enables deterministic backtesting. |
| **Compatibility with Dry‑Run / Paper Trading** – Any change must preserve a faithful simulation mode that mirrors live behavior (order sizing, timing, slippage approximations). | Allows validation without risking real capital. |

## 6. Components That Should Eventually Be Split into Separate Services
| Candidate | Reason for Separation | Suggested Interface |
|-----------|-----------------------|---------------------|
| **Market Data Collector & Cache** | High fan‑out; many strategies need the same ticks and derived indicators (VWAP, EMA, ATR, GEX). Centralizing reduces redundant network calls and provides a stable view of the market. | Subscribe to `market.tick` topic (Redis Streams/Kafka) or expose a gRPC/REST `GetBars(symbol, timeframe, limit)` method. |
| **Risk & Position Service** | Central authority for all risk limits; must be highly available and consistent across strategy instances. | gRPC `CheckOrder(OrderRequest) -> (Approved|Rejected, ModifiedOrder)`; also `UpdateRiskState(equity, drawdown)`. |
| **Strategy Orchestrator / Scheduler** | Responsible for launching, scaling, and monitoring strategy instances; can be swapped for different execution models (KJobs, serverless functions, etc.). | Receives schedule configs; emits `StartStrategy(schema, version)` and `StopStrategy(id)` events; returns health status. |
| **Broker Adapter Abstraction Layer** | Isolates broker‑specific quirks (order types, lot sizing, status codes) from the core; enables plug‑and‑play of new brokerages. | Abstract base `Broker` with methods `place_order(intent)`, `cancel(order_id)`, `get_position(symbol)`, `get_market_data(symbol, tf)`. |
| **State Persistence Layer** | Current per‑strategy JSON files are fragile and not shareable; a centralized store enables multi‑instance strategies (e.g., running the same strategy on two separate accounts for A/B testing). | Key‑value store API (`SET key value`, `GET key`, `DEL key`) with TTL support (Redis). |
| **Observability Pipeline (Logging/Metrics/Tracing)** | Separating concerns allows swapping back‑ends (e.g., from local file to Loki/Prometheus/Grafana/Otel) without touching application code. | Structured JSON logs to stdout; Prometheus exporter at `/metrics`; OpenTelemetry instrumentation for spans. |

### Migration Path (Incremental)
1. **Introduce a Cache Layer** – Wrap existing `get_bars` calls with a simple LRU/TTL cache (in‑process) to immediately reduce duplicate HTTP calls.  
2. **Extract Risk Computation** – Move the calculation of `RISK_SCALE`, daily/monthly kill checks into a pure function that receives the equity and returns a multiplier; keep the file‑based state for now but guard it with a file lock.  
3. **Create a Strategy Interface** – Define a Python abstract base class `Strategy` with a method `on_bar(data: dict) -> List[Intent]`. Refactor each `run_*` function into a subclass.  
4. **Add a Simple Orchestrator** – Write a lightweight loop that loads instantiated strategies, calls them in parallel (using `concurrent.futures.ThreadPoolExecutor`), aggregates intents, passes them through the risk function, then dispatches via the broker adapter.  
5. **Containerize** – Dockerize the orchestrator + each strategy plugin; push to a registry.  
6. **Deploy to Kubernetes** – Use a CronJob to start the orchestrator at the prescribed UTC times; scale the strategy pods as needed.  
7. **Add Observability** – Integrate OpenTelemetry instrumentation; expose Prometheus metrics; forward logs to a centralized Loki stack.  

Following this staged approach preserves the existing functional baseline while gradually moving toward the resilient, scalable architecture outlined above.

---

**End of CTO analysis**.  
*This document is intended to be used as a planning guide for the engineering team; implementation efforts should be prioritized based on risk reduction and development velocity.*