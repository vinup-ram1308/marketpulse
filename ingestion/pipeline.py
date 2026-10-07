"""Orchestrate one MarketPulse batch ingestion run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from ingestion.loader import RAW_PAYLOAD_COLUMNS, BigQueryRawLoader


@dataclass(frozen=True)
class IngestionResult:
    """Summary of one successful batch ingestion."""

    batch_id: str
    rows_received: int
    rows_loaded: int
    ingestion_timestamp: datetime
    table_id: str


def ingest_batch(
    dataframe: pd.DataFrame,
    loader: BigQueryRawLoader | None = None,
) -> IngestionResult:
    """Validate and append exactly one simulator batch to the RAW table."""
    if dataframe.empty:
        raise ValueError("Cannot ingest an empty DataFrame")

    if "batch_id" not in dataframe.columns:
        raise ValueError("DataFrame is missing the required 'batch_id' column")

    missing_columns = [
        column for column in RAW_PAYLOAD_COLUMNS if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            f"DataFrame is missing required ingestion columns: {missing_columns}"
        )

    batch_values = dataframe["batch_id"]
    if batch_values.isna().any() or batch_values.map(
        lambda value: not isinstance(value, str) or not value.strip()
    ).any():
        raise ValueError("DataFrame batch_id values must be present and non-empty")

    unique_batch_ids = batch_values.unique()
    if len(unique_batch_ids) != 1:
        raise ValueError("DataFrame must contain exactly one unique batch_id")

    batch_id = unique_batch_ids[0]
    rows_received = len(dataframe)
    ingestion_timestamp = datetime.now(timezone.utc)
    active_loader = loader if loader is not None else BigQueryRawLoader()
    active_loader.ensure_table()
    rows_loaded = active_loader.load_dataframe(dataframe)

    if rows_loaded != rows_received:
        raise RuntimeError(
            f"Loaded row count mismatch for batch {batch_id!r}: "
            f"received {rows_received}, loaded {rows_loaded}"
        )

    return IngestionResult(
        batch_id=batch_id,
        rows_received=rows_received,
        rows_loaded=rows_loaded,
        ingestion_timestamp=ingestion_timestamp,
        table_id=active_loader.settings.fully_qualified_table_id,
    )
