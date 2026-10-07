"""BigQuery configuration, client reuse, and safe query execution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import re
from typing import Sequence

from dotenv import load_dotenv
from google.cloud import bigquery


DEFAULT_PROJECT_ID = "marketpulse-510219"
DEFAULT_ANALYTICS_DATASET = "marketpulse_analytics"
DEFAULT_LOCATION = "asia-south1"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BigQuerySettings:
    """Trusted identifiers and location used by the analytics API."""

    project_id: str
    dataset_id: str
    location: str

    @classmethod
    def from_env(cls) -> BigQuerySettings:
        """Load project and dataset settings, using defaults only when absent."""
        load_dotenv()
        project_id = os.environ.get("GCP_PROJECT_ID", DEFAULT_PROJECT_ID).strip()
        dataset_id = os.environ.get(
            "BIGQUERY_ANALYTICS_DATASET", DEFAULT_ANALYTICS_DATASET
        ).strip()
        location = os.environ.get("BIGQUERY_LOCATION", DEFAULT_LOCATION).strip()

        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project_id):
            raise ValueError("GCP_PROJECT_ID must be a valid Google Cloud project ID")
        if not re.fullmatch(r"[A-Za-z0-9_]+", dataset_id):
            raise ValueError("BIGQUERY_ANALYTICS_DATASET must be a valid dataset ID")
        if not location:
            raise ValueError("BIGQUERY_LOCATION must not be empty")
        return cls(project_id, dataset_id, location)

    def table_id(self, table_name: str) -> str:
        """Build a quoted fully qualified table ID for a fixed table name."""
        if table_name not in {
            "mart_market_signals",
            "market_alerts",
        }:
            raise ValueError("Unsupported analytics table")
        return f"`{self.project_id}.{self.dataset_id}.{table_name}`"


@lru_cache(maxsize=1)
def get_bigquery_client() -> bigquery.Client:
    """Return the process-wide ADC-authenticated BigQuery client."""
    settings = BigQuerySettings.from_env()
    return bigquery.Client(
        project=settings.project_id,
        location=settings.location,
    )


def execute_query(
    client: bigquery.Client,
    sql: str,
    query_parameters: Sequence[bigquery.ScalarQueryParameter] = (),
) -> list[bigquery.Row]:
    """Run a parameterized query, returning a generic error on BigQuery failure."""
    try:
        job_config = bigquery.QueryJobConfig(
            query_parameters=list(query_parameters)
        )
        return list(client.query(sql, job_config=job_config).result())
    except Exception:
        logger.error("BigQuery analytics query failed.")
        raise RuntimeError("BigQuery analytics query failed") from None
