# MarketPulse — Automated Competitive Intelligence Pipeline

MarketPulse is an end-to-end competitive intelligence platform that simulates timestamped competitor observations, ingests them into BigQuery, transforms them with dbt, detects explainable market signals, exposes curated data through FastAPI, and presents the resulting intelligence through a React dashboard.

The project focuses on the engineering workflow behind competitive monitoring:

**Simulation → Ingestion → Warehouse → Orchestration → Transformation → Signal Detection → API → Dashboard**

MarketPulse tracks competitor pricing, inventory availability, and promotional activity across products and markets. It is designed to demonstrate how raw market observations can be transformed into concise, explainable signals that analysts can investigate.

> **Data source:** MarketPulse currently uses a deterministic synthetic market simulator rather than live competitor scraping. The simulator is intentionally designed so that it can be replaced by a real market-data source without requiring major changes to the downstream architecture.

---

## Why MarketPulse?

Competitive monitoring can generate a large number of individual observations without providing a clear picture of what actually changed.

MarketPulse addresses this by transforming observations into temporal market signals.

Instead of only answering:

> "What is the current competitor state?"

the system is designed to answer:

> "What changed compared with the previous observation, and is that change significant enough to investigate?"

The current signal engine focuses on four areas:

- Competitor price movement
- Promotion activity
- Inventory availability
- Price dispersion across competitors

The resulting alerts are rule-based and explainable. They describe competitor market conditions and do **not** compare competitors against an internal or owned price.

---

## At a Glance

- Reproducible, timestamp-keyed market snapshots generated from product and competitor catalogs.
- Deterministic market simulation using seeded randomness.
- Batch ingestion into a typed, partitioned BigQuery RAW table.
- Airflow orchestration of simulation, ingestion, dbt transformation, and validation.
- dbt staging, intermediate feature, market-signal, and alert models.
- Temporal feature engineering using previous market observations.
- Four explainable alert signal families.
- Read-only FastAPI endpoints backed by parameterized BigQuery queries.
- React + TypeScript dashboard for market monitoring and investigation.
- Product-level intelligence and alert drilldowns.
- Automated Python and frontend tests.
- Dockerized Airflow environment.
- Google Cloud / BigQuery-based analytical architecture.

---

# Architecture

```mermaid
flowchart LR

    Catalogs["Product & competitor catalogs"]
        --> Sim["Python market simulator"]

    Sim
        --> DAG["Airflow DAG"]

    DAG
        --> CSV["Timestamped batch CSV"]

    CSV
        --> Ingest["Python ingestion & validation"]

    Ingest
        --> Raw[("BigQuery RAW<br/>marketpulse_raw")]

    Raw
        --> Staging["dbt staging"]

    Staging
        --> Intermediate["dbt intermediate"]

    Intermediate
        --> Mart["mart_market_signals"]

    Mart
        --> Features["int_market_signal_features"]

    Features
        --> Alerts["market_alerts"]

    Mart
        --> API["FastAPI"]

    Alerts
        --> API

    API
        --> UI["React / TypeScript dashboard"]