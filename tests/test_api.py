"""Mock-only tests for MarketPulse API routes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from api.bigquery_client import get_bigquery_client
from api.main import app


@pytest.fixture
def mock_bigquery_client() -> MagicMock:
    """Override the API client dependency with an isolated BigQuery mock."""
    client = MagicMock()
    app.dependency_overrides[get_bigquery_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_bigquery_client, None)


@pytest.fixture
def test_client() -> TestClient:
    """Return an HTTP client for the local FastAPI application."""
    return TestClient(app)


def set_query_rows(client: MagicMock, rows: list[dict[str, object]]) -> None:
    """Configure the mocked BigQuery query result."""
    client.query.return_value.result.return_value = rows


def query_parameters(client: MagicMock) -> dict[str, object]:
    """Return submitted named query parameters keyed by parameter name."""
    config = client.query.call_args.kwargs["job_config"]
    return {parameter.name: parameter.value for parameter in config.query_parameters}


def test_health_endpoint(test_client: TestClient) -> None:
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "marketpulse-api"}


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)
def test_local_frontend_origin_receives_cors_headers(
    test_client: TestClient, origin: str
) -> None:
    response = test_client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "origin" in response.headers["vary"].lower()


def test_unlisted_origin_is_not_allowed_by_cors(test_client: TestClient) -> None:
    response = test_client.get(
        "/health",
        headers={"Origin": "http://localhost:5174"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_products_endpoint(
    test_client: TestClient, mock_bigquery_client: MagicMock
) -> None:
    set_query_rows(
        mock_bigquery_client,
        [
            {
                "product_id": "P001",
                "product_name": "Orion X Pro",
                "category": "Smartphones",
                "brand": "Orion",
            }
        ],
    )

    response = test_client.get("/products")

    assert response.status_code == 200
    assert response.json()[0]["product_id"] == "P001"
    sql = mock_bigquery_client.query.call_args.args[0]
    assert "SELECT DISTINCT product_id, product_name, category, brand" in sql
    assert "ORDER BY product_id" in sql


def test_market_signals_filtering(
    test_client: TestClient, mock_bigquery_client: MagicMock
) -> None:
    set_query_rows(
        mock_bigquery_client,
        [
            {
                "product_id": "P001",
                "product_name": "Orion X Pro",
                "category": "Smartphones",
                "brand": "Orion",
                "market": "US",
                "currency": "USD",
                "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
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
                "promotion_activity_flag": True,
            }
        ],
    )

    response = test_client.get(
        "/market-signals",
        params={
            "product_id": "P001' OR TRUE",
            "market": "US",
            "start_time": "2026-01-01T00:00:00Z",
            "end_time": "2026-01-02T00:00:00+00:00",
            "limit": 25,
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["lowest_competitor_price"] == 950.0
    sql = mock_bigquery_client.query.call_args.args[0]
    assert "product_id = @product_id" in sql
    assert "market = @market" in sql
    assert "observed_at >= @start_time" in sql
    assert "observed_at <= @end_time" in sql
    assert "P001' OR TRUE" not in sql
    params = query_parameters(mock_bigquery_client)
    assert params["product_id"] == "P001' OR TRUE"
    assert params["market"] == "US"
    assert params["start_time"].tzinfo is not None
    assert params["end_time"].tzinfo is not None
    assert params["limit"] == 25


def test_alerts_filtering(
    test_client: TestClient, mock_bigquery_client: MagicMock
) -> None:
    set_query_rows(
        mock_bigquery_client,
        [
            {
                "product_id": "P001",
                "product_name": "Orion X Pro",
                "market": "US",
                "currency": "USD",
                "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "signal_type": "PRICE_MOVEMENT",
                "severity": "MEDIUM",
                "message": "Average competitor price increased.",
            }
        ],
    )

    response = test_client.get(
        "/alerts",
        params={
            "product_id": "P001",
            "market": "US",
            "signal_type": "PRICE_MOVEMENT",
            "severity": "MEDIUM",
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["signal_type"] == "PRICE_MOVEMENT"
    params = query_parameters(mock_bigquery_client)
    assert params["product_id"] == "P001"
    assert params["market"] == "US"
    assert params["signal_type"] == "PRICE_MOVEMENT"
    assert params["severity"] == "MEDIUM"


def test_alert_summary(
    test_client: TestClient, mock_bigquery_client: MagicMock
) -> None:
    set_query_rows(
        mock_bigquery_client,
        [
            {
                "signal_type": "PRICE_MOVEMENT",
                "severity": "LOW",
                "alert_count": 2,
            },
            {
                "signal_type": "INVENTORY_PRESSURE",
                "severity": "HIGH",
                "alert_count": 1,
            },
        ],
    )

    response = test_client.get("/alerts/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total_alerts": 3,
        "counts": [
            {
                "signal_type": "PRICE_MOVEMENT",
                "severity": "LOW",
                "alert_count": 2,
            },
            {
                "signal_type": "INVENTORY_PRESSURE",
                "severity": "HIGH",
                "alert_count": 1,
            },
        ],
    }


@pytest.mark.parametrize(
    ("path", "parameter", "value"),
    [
        ("/market-signals", "limit", "0"),
        ("/market-signals", "limit", "101"),
        ("/alerts", "limit", "0"),
        ("/alerts", "limit", "101"),
    ],
)
def test_invalid_limit_is_rejected(
    test_client: TestClient,
    path: str,
    parameter: str,
    value: str,
) -> None:
    response = test_client.get(path, params={parameter: value})

    assert response.status_code == 422


def test_invalid_signal_type_is_rejected(test_client: TestClient) -> None:
    response = test_client.get("/alerts", params={"signal_type": "UNKNOWN"})

    assert response.status_code == 422


def test_invalid_severity_is_rejected(test_client: TestClient) -> None:
    response = test_client.get("/alerts", params={"severity": "CRITICAL"})

    assert response.status_code == 422


def test_reversed_mixed_timezone_range_is_rejected(test_client: TestClient) -> None:
    response = test_client.get(
        "/market-signals",
        params={
            "start_time": "2026-01-02T00:00:00",
            "end_time": "2026-01-01T18:59:00-05:00",
        },
    )

    assert response.status_code == 422
