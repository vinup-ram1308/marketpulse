"""Mock-only tests for BigQuery RAW loading and environment settings."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest
from google.api_core.exceptions import ServiceUnavailable
from google.cloud import bigquery

from config.settings import Settings
from ingestion.loader import RAW_PAYLOAD_COLUMNS, BigQueryRawLoader


ENVIRONMENT_SETTINGS = {
    "GCP_PROJECT_ID": "marketpulse-test",
    "BIGQUERY_DATASET": "marketpulse_raw",
    "BIGQUERY_TABLE": "raw_market_observations",
    "BIGQUERY_LOCATION": "asia-south1",
}
EXPECTED_SCHEMA = (
    ("observation_id", "STRING"),
    ("batch_id", "STRING"),
    ("product_id", "STRING"),
    ("product_name", "STRING"),
    ("category", "STRING"),
    ("brand", "STRING"),
    ("competitor_id", "STRING"),
    ("competitor_name", "STRING"),
    ("market", "STRING"),
    ("observed_at", "TIMESTAMP"),
    ("price", "NUMERIC"),
    ("currency", "STRING"),
    ("stock_status", "STRING"),
    ("stock_quantity", "INT64"),
    ("promotion_flag", "BOOL"),
    ("promotion_pct", "NUMERIC"),
    ("source", "STRING"),
    ("ingested_at", "TIMESTAMP"),
)


@pytest.fixture
def settings() -> Settings:
    """Return stable settings that do not depend on the local environment."""
    return Settings(
        project_id=ENVIRONMENT_SETTINGS["GCP_PROJECT_ID"],
        dataset_id=ENVIRONMENT_SETTINGS["BIGQUERY_DATASET"],
        table_id=ENVIRONMENT_SETTINGS["BIGQUERY_TABLE"],
        location=ENVIRONMENT_SETTINGS["BIGQUERY_LOCATION"],
    )


@pytest.fixture
def mock_client() -> MagicMock:
    """Return an injected BigQuery client double."""
    client = MagicMock()
    client.create_table.side_effect = lambda table, exists_ok: table
    return client


def sample_dataframe() -> pd.DataFrame:
    """Build representative rows including high-precision NUMERIC values."""
    return pd.DataFrame(
        [
            {
                "observation_id": "obs-exact-001",
                "batch_id": "batch-001",
                "product_id": "P001",
                "product_name": "Orion X Pro",
                "category": "Smartphones",
                "brand": "Orion",
                "competitor_id": "C001",
                "competitor_name": "Northstar Retail",
                "market": "US",
                "observed_at": datetime(
                    2026, 1, 1, 12, 30, 45, 123456, tzinfo=timezone.utc
                ),
                "price": Decimal("1299.123456789"),
                "currency": "USD",
                "stock_status": "IN_STOCK",
                "stock_quantity": 42,
                "promotion_flag": True,
                "promotion_pct": Decimal("12.345678901"),
                "source": "market_simulator",
            },
            {
                "observation_id": "obs-exact-002",
                "batch_id": "batch-001",
                "product_id": "P002",
                "product_name": "Orion X",
                "category": "Smartphones",
                "brand": "Orion",
                "competitor_id": "C002",
                "competitor_name": "MetroTech",
                "market": "US",
                "observed_at": datetime(
                    2026, 1, 1, 12, 30, 45, 654321, tzinfo=timezone.utc
                ),
                "price": 749.1234567890123,
                "currency": "USD",
                "stock_status": "LOW_STOCK",
                "stock_quantity": 4,
                "promotion_flag": False,
                "promotion_pct": 0.0,
                "source": "market_simulator",
            },
        ],
        columns=RAW_PAYLOAD_COLUMNS,
    )


def submitted_records(client: MagicMock) -> list[dict[str, object]]:
    """Decode the newline-delimited JSON submitted to the mocked client."""
    file_object = client.load_table_from_file.call_args.args[0]
    assert isinstance(file_object, BytesIO)
    return [
        json.loads(line)
        for line in file_object.getvalue().decode("utf-8").splitlines()
    ]


def test_settings_load_valid_environment_and_table_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.settings.load_dotenv", lambda: None)
    for name, value in ENVIRONMENT_SETTINGS.items():
        monkeypatch.setenv(name, value)

    settings = Settings.from_env()

    assert settings.project_id == "marketpulse-test"
    assert settings.dataset_id == "marketpulse_raw"
    assert settings.table_id == "raw_market_observations"
    assert settings.location == "asia-south1"
    assert settings.fully_qualified_table_id == (
        "marketpulse-test.marketpulse_raw.raw_market_observations"
    )


def test_settings_reject_missing_required_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("config.settings.load_dotenv", lambda: None)
    for name in ENVIRONMENT_SETTINGS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="GCP_PROJECT_ID.*BIGQUERY_LOCATION"):
        Settings.from_env()


def test_ensure_table_uses_configured_dataset_schema_and_partitioning(
    settings: Settings, mock_client: MagicMock
) -> None:
    loader = BigQueryRawLoader(settings=settings, client=mock_client)

    table = loader.ensure_table()

    dataset = mock_client.create_dataset.call_args.args[0]
    assert dataset.project == settings.project_id
    assert dataset.dataset_id == settings.dataset_id
    assert dataset.location == "asia-south1"
    mock_client.create_dataset.assert_called_once_with(dataset, exists_ok=True)

    assert table.project == settings.project_id
    assert table.dataset_id == settings.dataset_id
    assert table.table_id == settings.table_id
    assert [(field.name, field.field_type) for field in table.schema] == list(EXPECTED_SCHEMA)
    assert table.time_partitioning.field == "observed_at"
    assert table.time_partitioning.type_ == bigquery.TimePartitioningType.DAY
    mock_client.create_table.assert_called_once_with(table, exists_ok=True)


def test_load_dataframe_rejects_missing_columns(
    settings: Settings, mock_client: MagicMock
) -> None:
    loader = BigQueryRawLoader(settings=settings, client=mock_client)
    dataframe = sample_dataframe().drop(columns="category")

    with pytest.raises(ValueError, match="category"):
        loader.load_dataframe(dataframe)

    mock_client.load_table_from_file.assert_not_called()


def test_empty_dataframe_returns_zero_without_loading(
    settings: Settings, mock_client: MagicMock
) -> None:
    loader = BigQueryRawLoader(settings=settings, client=mock_client)

    assert loader.load_dataframe(sample_dataframe().iloc[0:0]) == 0

    mock_client.load_table_from_file.assert_not_called()


def test_load_dataframe_appends_json_preserving_ids_timestamps_and_ingestion_time(
    settings: Settings, mock_client: MagicMock
) -> None:
    loader = BigQueryRawLoader(settings=settings, client=mock_client)
    dataframe = sample_dataframe()
    expected_ids = dataframe["observation_id"].tolist()
    expected_timestamps = [value.isoformat() for value in dataframe["observed_at"]]
    load_job = mock_client.load_table_from_file.return_value
    load_job.output_rows = len(dataframe)
    load_job.result.return_value = None

    loaded_rows = loader.load_dataframe(dataframe)

    assert loaded_rows == len(dataframe)
    records = submitted_records(mock_client)
    assert len(records) == len(dataframe)
    assert [record["observation_id"] for record in records] == expected_ids
    assert [record["observed_at"] for record in records] == expected_timestamps
    for input_row, record in zip(dataframe.to_dict("records"), records):
        for column in RAW_PAYLOAD_COLUMNS:
            value = input_row[column]
            if column in {"price", "promotion_pct"}:
                expected_value = str(Decimal(str(value)))
            elif isinstance(value, datetime):
                expected_value = value.isoformat()
            else:
                expected_value = value
            assert record[column] == expected_value
    for record in records:
        ingestion_time = datetime.fromisoformat(record["ingested_at"])
        assert ingestion_time.tzinfo is not None
        assert ingestion_time.utcoffset() == timedelta(0)

    load_call = mock_client.load_table_from_file.call_args
    assert load_call.args[1] == settings.fully_qualified_table_id
    config = load_call.kwargs["job_config"]
    assert config.write_disposition == bigquery.WriteDisposition.WRITE_APPEND
    assert config.source_format == bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    assert [(field.name, field.field_type) for field in config.schema] == list(EXPECTED_SCHEMA)
    load_job.result.assert_called_once_with()


def test_load_dataframe_returns_load_job_output_rows(
    settings: Settings, mock_client: MagicMock
) -> None:
    load_job = mock_client.load_table_from_file.return_value
    load_job.output_rows = 17
    loader = BigQueryRawLoader(settings=settings, client=mock_client)

    assert loader.load_dataframe(sample_dataframe()) == 17
    assert len(sample_dataframe()) != load_job.output_rows
    load_job.result.assert_called_once_with()


def test_load_dataframe_requires_reported_output_rows(
    settings: Settings, mock_client: MagicMock
) -> None:
    load_job = mock_client.load_table_from_file.return_value
    load_job.output_rows = None
    loader = BigQueryRawLoader(settings=settings, client=mock_client)

    with pytest.raises(RuntimeError, match="without reporting output_rows"):
        loader.load_dataframe(sample_dataframe())
    load_job.result.assert_called_once_with()


def test_numeric_fields_are_serialized_without_rounding(
    settings: Settings, mock_client: MagicMock
) -> None:
    loader = BigQueryRawLoader(settings=settings, client=mock_client)

    loader.load_dataframe(sample_dataframe())

    records = submitted_records(mock_client)
    assert records[0]["price"] == "1299.123456789"
    assert records[0]["promotion_pct"] == "12.345678901"
    assert records[1]["price"] == "749.1234567890123"
    assert records[1]["promotion_pct"] == "0.0"


@pytest.mark.parametrize("failure_stage", ["start", "result"])
def test_bigquery_errors_are_propagated(
    settings: Settings, mock_client: MagicMock, failure_stage: str
) -> None:
    loader = BigQueryRawLoader(settings=settings, client=mock_client)
    error = ServiceUnavailable("BigQuery unavailable")
    if failure_stage == "start":
        mock_client.load_table_from_file.side_effect = error
    else:
        mock_client.load_table_from_file.return_value.result.side_effect = error

    with pytest.raises(ServiceUnavailable, match="BigQuery unavailable"):
        loader.load_dataframe(sample_dataframe())


def test_dataset_creation_errors_are_propagated(
    settings: Settings, mock_client: MagicMock
) -> None:
    mock_client.create_dataset.side_effect = ServiceUnavailable("Dataset API unavailable")
    loader = BigQueryRawLoader(settings=settings, client=mock_client)

    with pytest.raises(ServiceUnavailable, match="Dataset API unavailable"):
        loader.ensure_table()
