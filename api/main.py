"""FastAPI endpoints for MarketPulse curated analytics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery

from api.bigquery_client import (
    BigQuerySettings,
    execute_query,
    get_bigquery_client,
)
from api.models import (
    AlertCountResponse,
    AlertResponse,
    AlertSummaryResponse,
    HealthResponse,
    MarketSignalResponse,
    ProductResponse,
    Severity,
    SignalType,
)


app = FastAPI(
    title="MarketPulse API",
    description="Read-only API for MarketPulse competitive market analytics.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)


def _rows_as_dicts(rows: list[bigquery.Row]) -> list[dict[str, Any]]:
    """Convert BigQuery rows to response-model input mappings."""
    return [dict(row.items()) for row in rows]


def _timestamp_parameter_value(value: datetime) -> datetime:
    """Normalize an ISO datetime filter to UTC for BigQuery TIMESTAMP params."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _add_time_filters(
    predicates: list[str],
    parameters: list[bigquery.ScalarQueryParameter],
    start_time: datetime | None,
    end_time: datetime | None,
) -> None:
    """Append parameterized inclusive timestamp range conditions."""
    if start_time is not None:
        predicates.append("observed_at >= @start_time")
        parameters.append(
            bigquery.ScalarQueryParameter(
                "start_time", "TIMESTAMP", _timestamp_parameter_value(start_time)
            )
        )
    if end_time is not None:
        predicates.append("observed_at <= @end_time")
        parameters.append(
            bigquery.ScalarQueryParameter(
                "end_time", "TIMESTAMP", _timestamp_parameter_value(end_time)
            )
        )


def _query_or_http_500(
    client: bigquery.Client,
    sql: str,
    parameters: list[bigquery.ScalarQueryParameter],
) -> list[dict[str, Any]]:
    try:
        return _rows_as_dicts(execute_query(client, sql, parameters))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve MarketPulse analytics right now.",
        ) from None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return process health without contacting BigQuery."""
    return HealthResponse(status="ok", service="marketpulse-api")


@app.get("/products", response_model=list[ProductResponse])
def products(
    client: Annotated[bigquery.Client, Depends(get_bigquery_client)],
) -> list[dict[str, Any]]:
    """List product dimensions present in market snapshots."""
    table = BigQuerySettings.from_env().table_id("mart_market_signals")
    sql = f"""
        SELECT DISTINCT product_id, product_name, category, brand
        FROM {table}
        ORDER BY product_id
    """
    return _query_or_http_500(client, sql, [])


@app.get("/market-signals", response_model=list[MarketSignalResponse])
def market_signals(
    client: Annotated[bigquery.Client, Depends(get_bigquery_client)],
    product_id: str | None = None,
    market: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[dict[str, Any]]:
    """Read latest market snapshots with optional parameterized filters."""
    if (
        start_time is not None
        and end_time is not None
        and _timestamp_parameter_value(start_time)
        > _timestamp_parameter_value(end_time)
    ):
        raise HTTPException(
            status_code=422,
            detail="start_time must be less than or equal to end_time.",
        )

    settings = BigQuerySettings.from_env()
    table = settings.table_id("mart_market_signals")
    predicates: list[str] = []
    parameters: list[bigquery.ScalarQueryParameter] = []
    for name, value in (("product_id", product_id), ("market", market)):
        if value is not None:
            predicates.append(f"{name} = @{name}")
            parameters.append(bigquery.ScalarQueryParameter(name, "STRING", value))
    _add_time_filters(predicates, parameters, start_time, end_time)
    where_clause = f"WHERE {' AND '.join(predicates)}" if predicates else ""

    sql = f"""
        SELECT
            product_id,
            product_name,
            category,
            brand,
            market,
            currency,
            observed_at,
            competitor_count,
            avg_competitor_price,
            min_competitor_price,
            max_competitor_price,
            price_spread,
            price_spread_pct,
            lowest_price_competitor_name AS lowest_competitor_name,
            lowest_price AS lowest_competitor_price,
            highest_price_competitor_name AS highest_competitor_name,
            highest_price AS highest_competitor_price,
            in_stock_pct,
            promotion_competitor_pct,
            market_price_pressure,
            promotion_activity_flag
        FROM {table}
        {where_clause}
        ORDER BY observed_at DESC
        LIMIT @limit
    """
    parameters.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
    return _query_or_http_500(client, sql, parameters)


@app.get("/alerts", response_model=list[AlertResponse])
def alerts(
    client: Annotated[bigquery.Client, Depends(get_bigquery_client)],
    product_id: str | None = None,
    market: str | None = None,
    signal_type: SignalType | None = None,
    severity: Severity | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[dict[str, Any]]:
    """Read latest alerts with optional parameterized filters."""
    if (
        start_time is not None
        and end_time is not None
        and _timestamp_parameter_value(start_time)
        > _timestamp_parameter_value(end_time)
    ):
        raise HTTPException(
            status_code=422,
            detail="start_time must be less than or equal to end_time.",
        )

    table = BigQuerySettings.from_env().table_id("market_alerts")
    predicates: list[str] = []
    parameters: list[bigquery.ScalarQueryParameter] = []
    for name, value in (
        ("product_id", product_id),
        ("market", market),
        ("signal_type", signal_type),
        ("severity", severity),
    ):
        if value is not None:
            predicates.append(f"{name} = @{name}")
            parameters.append(bigquery.ScalarQueryParameter(name, "STRING", value))
    _add_time_filters(predicates, parameters, start_time, end_time)
    where_clause = f"WHERE {' AND '.join(predicates)}" if predicates else ""

    sql = f"""
        SELECT
            product_id,
            product_name,
            market,
            currency,
            observed_at,
            signal_type,
            severity,
            message
        FROM {table}
        {where_clause}
        ORDER BY observed_at DESC
        LIMIT @limit
    """
    parameters.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
    return _query_or_http_500(client, sql, parameters)


@app.get("/alerts/summary", response_model=AlertSummaryResponse)
def alert_summary(
    client: Annotated[bigquery.Client, Depends(get_bigquery_client)],
) -> AlertSummaryResponse:
    """Count alerts by signal type and severity."""
    table = BigQuerySettings.from_env().table_id("market_alerts")
    sql = f"""
        SELECT signal_type, severity, COUNT(*) AS alert_count
        FROM {table}
        GROUP BY signal_type, severity
        ORDER BY signal_type, severity
    """
    rows = _query_or_http_500(client, sql, [])
    counts = [AlertCountResponse(**row) for row in rows]
    return AlertSummaryResponse(
        total_alerts=sum(item.alert_count for item in counts),
        counts=counts,
    )
