"""Append validated market observations to the BigQuery RAW table."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Final

import pandas as pd
from google.cloud import bigquery

from config.settings import Settings, get_settings


RAW_SCHEMA: Final[tuple[bigquery.SchemaField, ...]] = (
	bigquery.SchemaField("observation_id", "STRING"),
	bigquery.SchemaField("batch_id", "STRING"),
	bigquery.SchemaField("product_id", "STRING"),
	bigquery.SchemaField("product_name", "STRING"),
	bigquery.SchemaField("category", "STRING"),
	bigquery.SchemaField("brand", "STRING"),
	bigquery.SchemaField("competitor_id", "STRING"),
	bigquery.SchemaField("competitor_name", "STRING"),
	bigquery.SchemaField("market", "STRING"),
	bigquery.SchemaField("observed_at", "TIMESTAMP"),
	bigquery.SchemaField("price", "NUMERIC"),
	bigquery.SchemaField("currency", "STRING"),
	bigquery.SchemaField("stock_status", "STRING"),
	bigquery.SchemaField("stock_quantity", "INT64"),
	bigquery.SchemaField("promotion_flag", "BOOL"),
	bigquery.SchemaField("promotion_pct", "NUMERIC"),
	bigquery.SchemaField("source", "STRING"),
	bigquery.SchemaField("ingested_at", "TIMESTAMP"),
)
RAW_PAYLOAD_COLUMNS: Final[tuple[str, ...]] = tuple(
	field.name for field in RAW_SCHEMA if field.name != "ingested_at"
)
RAW_SCHEMA_COLUMNS: Final[tuple[str, ...]] = tuple(field.name for field in RAW_SCHEMA)


class BigQueryRawLoader:
	"""Create and append to the configured, partitioned BigQuery RAW table."""

	def __init__(
		self,
		settings: Settings | None = None,
		client: bigquery.Client | None = None,
	) -> None:
		"""Initialize using ADC unless a BigQuery-compatible client is injected."""
		self.settings = settings or get_settings()
		self.client = (
			client
			if client is not None
			else bigquery.Client(
				project=self.settings.project_id,
				location=self.settings.location,
			)
		)

	def ensure_table(self) -> bigquery.Table:
		"""Create the configured dataset and daily-partitioned RAW table if absent."""
		dataset_id = f"{self.settings.project_id}.{self.settings.dataset_id}"
		dataset = bigquery.Dataset(dataset_id)
		dataset.location = self.settings.location
		self.client.create_dataset(dataset, exists_ok=True)

		table = bigquery.Table(
			self.settings.fully_qualified_table_id,
			schema=RAW_SCHEMA,
		)
		table.time_partitioning = bigquery.TimePartitioning(
			type_=bigquery.TimePartitioningType.DAY,
			field="observed_at",
		)
		return self.client.create_table(table, exists_ok=True)

	def load_dataframe(self, dataframe: pd.DataFrame) -> int:
		"""Validate and append a DataFrame, returning its loaded row count."""
		missing = [
			column for column in RAW_PAYLOAD_COLUMNS if column not in dataframe.columns
		]
		if missing:
			raise ValueError(f"DataFrame is missing required columns: {missing}")

		allowed_columns = set(RAW_SCHEMA_COLUMNS)
		unexpected = [column for column in dataframe.columns if column not in allowed_columns]
		if unexpected:
			raise ValueError(f"DataFrame contains unsupported columns: {unexpected}")

		self._validate_utc_timestamps(dataframe["observed_at"], "observed_at")
		if dataframe.empty:
			return 0

		load_frame = dataframe.copy()
		load_frame["ingested_at"] = datetime.now(timezone.utc)
		load_frame = load_frame.loc[:, RAW_SCHEMA_COLUMNS]
		records = [self._serialize_record(record) for record in load_frame.to_dict("records")]
		payload = "\n".join(
			json.dumps(record, separators=(",", ":"), allow_nan=False)
			for record in records
		).encode("utf-8")
		job_config = bigquery.LoadJobConfig(
			schema=RAW_SCHEMA,
			write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
			source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
		)
		job = self.client.load_table_from_file(
			BytesIO(payload),
			self.settings.fully_qualified_table_id,
			rewind=True,
			size=len(payload),
			job_config=job_config,
		)
		job.result()
		if job.output_rows is None:
			raise RuntimeError("BigQuery load job completed without reporting output_rows")
		return job.output_rows

	@staticmethod
	def _serialize_record(record: dict[str, object]) -> dict[str, object]:
		"""Convert DataFrame scalars into loss-aware BigQuery JSON values."""
		serialized: dict[str, object] = {}
		for column, value in record.items():
			if value is None or pd.isna(value):
				serialized[column] = None
			elif column in {"price", "promotion_pct"}:
				try:
					numeric_value = Decimal(str(value))
				except (InvalidOperation, ValueError) as error:
					raise ValueError(f"Column {column!r} must contain numeric values") from error
				if not numeric_value.is_finite():
					raise ValueError(f"Column {column!r} must contain finite numeric values")
				serialized[column] = str(numeric_value)
			elif isinstance(value, datetime):
				serialized[column] = value.isoformat()
			elif isinstance(value, (str, int, float, bool)):
				serialized[column] = value
			elif hasattr(value, "item"):
				serialized[column] = value.item()
			else:
				raise ValueError(
					f"Column {column!r} contains unsupported value type "
					f"{type(value).__name__}"
				)
		return serialized

	@staticmethod
	def _validate_utc_timestamps(values: pd.Series, column: str) -> None:
		"""Require non-null values to be timezone-aware UTC without converting them."""
		for value in values:
			if pd.isna(value):
				raise ValueError(f"DataFrame column {column!r} contains a missing timestamp")
			if not isinstance(value, datetime):
				raise ValueError(f"DataFrame column {column!r} must contain timestamps")
			if value.tzinfo is None or value.utcoffset() != timedelta(0):
				raise ValueError(
					f"DataFrame column {column!r} must contain timezone-aware UTC timestamps"
				)
