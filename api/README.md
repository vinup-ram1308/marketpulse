# MarketPulse API

Read-only FastAPI endpoints for the curated BigQuery analytics tables. For the
overall system flow and quickstart, see the root [README](../README.md) and
[architecture notes](../docs/architecture.md).

## Configuration and local run

The API uses Google Application Default Credentials (ADC). It reads an optional
repository `.env` file and supports:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GCP_PROJECT_ID` | `marketpulse-510219` | BigQuery project. |
| `BIGQUERY_ANALYTICS_DATASET` | `marketpulse_analytics` | Curated dbt dataset. |
| `BIGQUERY_LOCATION` | `asia-south1` | BigQuery job/client location. |

Data endpoints need ADC with access to the curated tables. `/health` is a
process health response and does not contact BigQuery. To initialize ADC with
the Google Cloud CLI, run `gcloud auth application-default login`.

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

Install dependencies if needed with
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r api/requirements.txt`.

## Endpoints

All endpoints use JSON responses. `/market-signals` and `/alerts` are ordered
by newest `observed_at` first and default to 100 records; their `limit` must
be from 1 through 100. `/products` has no limit parameter and is ordered by
`product_id`. `start_time` and `end_time` accept ISO-8601 datetimes and are
inclusive. The API uses BigQuery query parameters for filter values.

### `GET /health`

No query parameters. Does not require BigQuery access.

```json
{"status":"ok","service":"marketpulse-api"}
```

### `GET /products`

No query parameters. Returns distinct product dimensions ordered by
`product_id`.

```json
[
  {
    "product_id": "P001",
    "product_name": "Orion X Pro",
    "category": "Smartphones",
    "brand": "Orion"
  }
]
```

### `GET /market-signals`

Optional query parameters:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `product_id` | string | Restrict to one product. |
| `market` | string | Restrict to one market. |
| `start_time` | ISO-8601 datetime | Inclusive lower bound for `observed_at`. |
| `end_time` | ISO-8601 datetime | Inclusive upper bound for `observed_at`. |
| `limit` | integer, 1–100 | Maximum number of records; default 100. |

Response fields: `product_id`, `product_name`, `category`, `brand`, `market`,
`currency`, `observed_at`, `competitor_count`, `avg_competitor_price`,
`min_competitor_price`, `max_competitor_price`, `price_spread`,
`price_spread_pct`, `lowest_competitor_name`, `lowest_competitor_price`,
`highest_competitor_name`, `highest_competitor_price`, `in_stock_pct`,
`promotion_competitor_pct`, `market_price_pressure`, and
`promotion_activity_flag`.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/market-signals?product_id=P001&market=US&limit=5"
```

Example response (one record; numeric values shown are illustrative schema
examples, not a live-data guarantee):

```json
[
  {
    "product_id": "P001",
    "product_name": "Orion X Pro",
    "category": "Smartphones",
    "brand": "Orion",
    "market": "US",
    "currency": "USD",
    "observed_at": "2026-01-01T00:00:00Z",
    "competitor_count": 4,
    "avg_competitor_price": 999.0,
    "min_competitor_price": 950.0,
    "max_competitor_price": 1050.0,
    "price_spread": 100.0,
    "price_spread_pct": 10.01,
    "lowest_competitor_name": "Northstar Retail",
    "lowest_competitor_price": 950.0,
    "highest_competitor_name": "Value Circuit",
    "highest_competitor_price": 1050.0,
    "in_stock_pct": 75.0,
    "promotion_competitor_pct": 25.0,
    "market_price_pressure": 0.1001,
    "promotion_activity_flag": true
  }
]
```

### `GET /alerts`

Optional query parameters:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `product_id` | string | Restrict to one product. |
| `market` | string | Restrict to one market. |
| `signal_type` | enum | `PRICE_MOVEMENT`, `PROMOTION_SURGE`, `INVENTORY_PRESSURE`, or `PRICE_DISPERSION`. |
| `severity` | enum | `LOW`, `MEDIUM`, or `HIGH`. |
| `start_time` | ISO-8601 datetime | Inclusive lower bound for `observed_at`. |
| `end_time` | ISO-8601 datetime | Inclusive upper bound for `observed_at`. |
| `limit` | integer, 1–100 | Maximum number of records; default 100. |

Response fields: `product_id`, `product_name`, `market`, `currency`,
`observed_at`, `signal_type`, `severity`, and `message`.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/alerts?signal_type=INVENTORY_PRESSURE&severity=HIGH&limit=10"
```

```json
[
  {
    "product_id": "P001",
    "product_name": "Orion X Pro",
    "market": "US",
    "currency": "USD",
    "observed_at": "2026-01-01T00:00:00Z",
    "signal_type": "INVENTORY_PRESSURE",
    "severity": "HIGH",
    "message": "Competitors in stock decreased from 100.00% to 25.00%, a decline of 75.00 percentage points."
  }
]
```

The sample message describes response shape only; returned values depend on
current warehouse data.

### `GET /alerts/summary`

No query parameters. Returns alert counts from the full alert table, grouped
by signal type and severity (not affected by `/alerts` filters).

```json
{
  "total_alerts": 5,
  "counts": [
    {"signal_type": "INVENTORY_PRESSURE", "severity": "HIGH", "alert_count": 1},
    {"signal_type": "PRICE_MOVEMENT", "severity": "LOW", "alert_count": 4}
  ]
}
```

Counts in this example are illustrative, not a live-data guarantee.

Invalid enum values, invalid limits, malformed timestamps, and reversed time
ranges return HTTP 422. BigQuery failures return a non-sensitive HTTP 500
message; SQL and credential details are not returned.

## Local browser CORS

For local Vite development only, the API allows these origins:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Other origins are not granted CORS access. Wildcard origins are not enabled.
Production browser origins require an explicit deployment-specific change.

## API tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q
```
