"""Mocked tests for one-batch ingestion orchestration."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from ingestion.pipeline import IngestionResult, ingest_batch


TABLE_ID = "marketpulse-test.marketpulse_raw.raw_market_observations"


@pytest.fixture
def dataframe() -> pd.DataFrame:
    """Return a small valid two-row batch without invoking the simulator."""
    return pd.DataFrame(
        [
            {
                "observation_id": "observation-001",
                "batch_id": "batch-exact-001",
                "product_id": "P001",
                "product_name": "Orion X Pro",
                "category": "Smartphones",
                "brand": "Orion",
                "competitor_id": "C001",
                "competitor_name": "Northstar Retail",
                "market": "US",
                "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "price": 999.0,
                "currency": "USD",
                "stock_status": "IN_STOCK",
                "stock_quantity": 30,
                "promotion_flag": False,
                "promotion_pct": 0.0,
                "source": "market_simulator",
            },
            {
                "observation_id": "observation-002",
                "batch_id": "batch-exact-001",
                "product_id": "P002",
                "product_name": "Orion X",
                "category": "Smartphones",
                "brand": "Orion",
                "competitor_id": "C002",
                "competitor_name": "MetroTech",
                "market": "US",
                "observed_at": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                "price": 749.0,
                "currency": "USD",
                "stock_status": "LOW_STOCK",
                "stock_quantity": 4,
                "promotion_flag": True,
                "promotion_pct": 10.0,
                "source": "market_simulator",
            },
        ]
    )


@pytest.fixture
def mock_loader() -> MagicMock:
    """Return a loader double with the RAW table identity configured."""
    loader = MagicMock()
    loader.settings = SimpleNamespace(fully_qualified_table_id=TABLE_ID)
    loader.load_dataframe.return_value = 2
    return loader


def test_successful_ingestion_returns_result_and_calls_loader_once(
    dataframe: pd.DataFrame, mock_loader: MagicMock
) -> None:
    result = ingest_batch(dataframe, loader=mock_loader)

    assert isinstance(result, IngestionResult)
    assert result.batch_id == "batch-exact-001"
    assert result.rows_received == 2
    assert result.rows_loaded == 2
    assert result.table_id == TABLE_ID
    assert result.ingestion_timestamp.tzinfo is not None
    assert result.ingestion_timestamp.utcoffset().total_seconds() == 0
    mock_loader.ensure_table.assert_called_once_with()
    mock_loader.load_dataframe.assert_called_once()
    assert mock_loader.load_dataframe.call_args.args[0] is dataframe


def test_ingestion_result_is_immutable(
    dataframe: pd.DataFrame, mock_loader: MagicMock
) -> None:
    result = ingest_batch(dataframe, loader=mock_loader)

    with pytest.raises(AttributeError):
        result.batch_id = "changed"  # type: ignore[misc]


def test_empty_dataframe_is_rejected(mock_loader: MagicMock, dataframe: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="empty DataFrame"):
        ingest_batch(dataframe.iloc[0:0], loader=mock_loader)

    mock_loader.ensure_table.assert_not_called()
    mock_loader.load_dataframe.assert_not_called()


def test_missing_batch_id_is_rejected(
    dataframe: pd.DataFrame, mock_loader: MagicMock
) -> None:
    with pytest.raises(ValueError, match="missing.*batch_id"):
        ingest_batch(dataframe.drop(columns="batch_id"), loader=mock_loader)

    mock_loader.ensure_table.assert_not_called()
    mock_loader.load_dataframe.assert_not_called()


def test_missing_other_required_column_is_rejected(
    dataframe: pd.DataFrame, mock_loader: MagicMock
) -> None:
    with pytest.raises(ValueError, match="market"):
        ingest_batch(dataframe.drop(columns="market"), loader=mock_loader)


def test_multiple_batch_ids_are_rejected(
    dataframe: pd.DataFrame, mock_loader: MagicMock
) -> None:
    mixed_batches = dataframe.copy()
    mixed_batches.loc[mixed_batches.index[-1], "batch_id"] = "batch-other"

    with pytest.raises(ValueError, match="exactly one unique batch_id"):
        ingest_batch(mixed_batches, loader=mock_loader)

    mock_loader.ensure_table.assert_not_called()
    mock_loader.load_dataframe.assert_not_called()


def test_loaded_row_count_mismatch_raises_runtime_error(
    dataframe: pd.DataFrame, mock_loader: MagicMock
) -> None:
    mock_loader.load_dataframe.return_value = 1

    with pytest.raises(RuntimeError, match="received 2, loaded 1"):
        ingest_batch(dataframe, loader=mock_loader)

    mock_loader.ensure_table.assert_called_once_with()
    mock_loader.load_dataframe.assert_called_once()
