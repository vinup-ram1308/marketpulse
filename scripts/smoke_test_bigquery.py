"""Run one scoped live smoke test against the configured BigQuery RAW table."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

from config.settings import get_settings
from ingestion.loader import BigQueryRawLoader
from simulator.market_simulator import MarketSimulator


EXPECTED_DATASET = "marketpulse_raw"
EXPECTED_TABLE = "raw_market_observations"
EXPECTED_ROWS = 48
OBSERVED_AT = datetime.now(timezone.utc).replace(
    minute=0,
    second=0,
    microsecond=0,
)


def run_smoke_test() -> None:
    """Generate, append, and verify one batch without scanning unrelated rows."""
    settings = get_settings()
    if (settings.dataset_id, settings.table_id) != (EXPECTED_DATASET, EXPECTED_TABLE):
        raise ValueError(
            "Smoke test requires BIGQUERY_DATASET=marketpulse_raw and "
            "BIGQUERY_TABLE=raw_market_observations"
        )

    simulator = MarketSimulator(seed=42)
    observations = simulator.generate_batch(OBSERVED_AT)
    generated_rows = len(observations)
    assert generated_rows == EXPECTED_ROWS
    batch_ids = observations["batch_id"].unique()
    assert len(batch_ids) == 1
    batch_id = str(batch_ids[0])

    loader = BigQueryRawLoader(settings=settings)
    loader.ensure_table()
    loaded_rows = loader.load_dataframe(observations)

    query = f"""
        SELECT
          COUNT(*) AS row_count,
          COUNT(DISTINCT observation_id) AS distinct_observation_count,
          MIN(observed_at) AS min_observed_at,
          MAX(observed_at) AS max_observed_at
        FROM `{settings.fully_qualified_table_id}`
        WHERE batch_id = @batch_id
    """
    query_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("batch_id", "STRING", batch_id),
        ]
    )
    query_job = loader.client.query(query, job_config=query_config)
    result_rows = list(query_job.result())
    if len(result_rows) != 1:
        raise RuntimeError(
            f"Expected one aggregate query result row, received {len(result_rows)}"
        )
    result = result_rows[0]

    print(f"Project ID: {settings.project_id}")
    print(f"Dataset ID: {settings.dataset_id}")
    print(f"Table ID: {settings.table_id}")
    print(f"Batch ID: {batch_id}")
    print(f"Observed at: {OBSERVED_AT.isoformat()}")
    print(f"Rows generated: {generated_rows}")
    print(f"Rows loaded: {loaded_rows}")
    print(f"Queried row count: {result.row_count}")
    print(f"Distinct observation count: {result.distinct_observation_count}")
    print(f"Minimum observed_at: {result.min_observed_at}")
    print(f"Maximum observed_at: {result.max_observed_at}")

    assert loaded_rows == EXPECTED_ROWS
    assert result.row_count == EXPECTED_ROWS
    assert result.distinct_observation_count == EXPECTED_ROWS
    assert result.min_observed_at == OBSERVED_AT
    assert result.max_observed_at == OBSERVED_AT
    print("Final verification: PASS")


def main() -> int:
    """Run the one-batch smoke test and report cloud/authentication errors."""
    try:
        run_smoke_test()
    except (DefaultCredentialsError, GoogleAPICallError, ValueError) as error:
        print(
            f"BigQuery smoke test failed ({type(error).__name__}): {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
