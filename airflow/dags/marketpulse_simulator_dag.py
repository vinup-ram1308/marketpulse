"""Generate, ingest, and verify one MarketPulse market-data batch."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import dag, task
from airflow.providers.standard.operators.bash import BashOperator


DATA_DIRECTORY = Path("/opt/airflow/marketpulse/data")
EXPECTED_ROWS = 48
EXPECTED_PRODUCTS = 12
EXPECTED_COMPETITORS = 4
RAW_TABLE_ID = "marketpulse-510219.marketpulse_raw.raw_market_observations"


@dag(
    dag_id="marketpulse_simulator_test",
    schedule=None,
    catchup=False,
    default_args={
        "owner": "marketpulse",
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["marketpulse", "ingestion", "local-test"],
)
def marketpulse_simulator_test() -> None:
    """Generate a simulator batch, ingest it, and verify its BigQuery rows."""

    @task(task_id="generate_market_batch")
    def generate_market_batch() -> dict[str, str | int]:
        """Generate and inspect one batch without sending its DataFrame to XCom."""
        from simulator.market_simulator import MarketSimulator

        observed_at = datetime.now(timezone.utc).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        observations = MarketSimulator(seed=42).generate_batch(observed_at)

        rows = len(observations)
        product_count = int(observations["product_id"].nunique())
        competitor_count = int(observations["competitor_id"].nunique())
        batch_ids = observations["batch_id"].unique()

        if rows != EXPECTED_ROWS:
            raise ValueError(f"Expected 48 observations, received {rows}")
        if (
            product_count != EXPECTED_PRODUCTS
            or competitor_count != EXPECTED_COMPETITORS
        ):
            raise ValueError(
                "Expected 12 products x 4 competitors, received "
                f"{product_count} products x {competitor_count} competitors"
            )
        if len(batch_ids) != 1:
            raise ValueError(f"Expected one batch ID, received {len(batch_ids)}")
        timestamps_are_utc = observations["observed_at"].map(
            lambda timestamp: timestamp.tzinfo is not None
            and timestamp.utcoffset() == timedelta(0)
        )
        if not timestamps_are_utc.all():
            raise ValueError("All observation timestamps must be timezone-aware UTC")

        batch_id = str(batch_ids[0])
        DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
        file_path = DATA_DIRECTORY / f"market_batch_{batch_id}.csv"
        observations.to_csv(file_path, index=False)

        print(f"batch_id: {batch_id}")
        print(f"observed_at: {observed_at.isoformat()}")
        print(f"observations: {rows}")
        print(f"unique products: {product_count}")
        print(f"unique competitors: {competitor_count}")
        print(f"csv_path: {file_path}")

        return {
            "batch_id": batch_id,
            "file_path": str(file_path),
            "row_count": rows,
            "observed_at": observed_at.isoformat(),
        }

    @task(task_id="ingest_market_batch")
    def ingest_market_batch(metadata: dict[str, str | int]) -> dict[str, str | int]:
        """Read the saved CSV and ingest it through the existing pipeline API."""
        import pandas as pd

        from ingestion.pipeline import ingest_batch

        batch_id = metadata.get("batch_id")
        file_path = metadata.get("file_path")
        row_count = metadata.get("row_count")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("Generated batch metadata is missing batch_id")
        if not isinstance(file_path, str) or not file_path:
            raise ValueError("Generated batch metadata is missing file_path")
        if not isinstance(row_count, int):
            raise ValueError("Generated batch metadata has an invalid row_count")

        observations = pd.read_csv(file_path, parse_dates=["observed_at"])
        observations["observed_at"] = pd.to_datetime(
            observations["observed_at"], utc=True
        )
        result = ingest_batch(observations)

        if result.batch_id != batch_id:
            raise RuntimeError(
                f"Ingestion returned batch {result.batch_id!r}; expected {batch_id!r}"
            )
        if result.rows_received != row_count or result.rows_loaded != row_count:
            raise RuntimeError(
                f"Ingestion row count mismatch for batch {batch_id!r}: "
                f"expected {row_count}, received {result.rows_received}, "
                f"loaded {result.rows_loaded}"
            )
        if result.table_id != RAW_TABLE_ID:
            raise RuntimeError(
                f"Ingestion targeted {result.table_id!r}; expected {RAW_TABLE_ID!r}"
            )

        print(f"Ingested batch {batch_id}: {result.rows_loaded} rows")
        return {
            "batch_id": result.batch_id,
            "row_count": result.rows_loaded,
            "table_id": result.table_id,
        }

    @task(task_id="validate_bigquery_load")
    def validate_bigquery_load(metadata: dict[str, str | int]) -> None:
        """Verify this batch's row count, observation IDs, and timestamps in BigQuery."""
        from google.cloud import bigquery

        from ingestion.loader import BigQueryRawLoader

        batch_id = metadata.get("batch_id")
        row_count = metadata.get("row_count")
        table_id = metadata.get("table_id")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("Ingestion metadata is missing batch_id")
        if row_count != EXPECTED_ROWS:
            raise ValueError(
                f"Expected {EXPECTED_ROWS} loaded rows, received {row_count}"
            )
        if table_id != RAW_TABLE_ID:
            raise ValueError(f"Unexpected ingestion table: {table_id!r}")

        query = f"""
            SELECT
              COUNT(*) AS row_count,
              COUNT(DISTINCT observation_id) AS distinct_observation_count,
              COUNTIF(observed_at IS NULL) AS missing_observed_at_count
            FROM `{RAW_TABLE_ID}`
            WHERE batch_id = @batch_id
        """
        query_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("batch_id", "STRING", batch_id)
            ]
        )
        loader = BigQueryRawLoader()
        rows = list(loader.client.query(query, job_config=query_config).result())
        if len(rows) != 1:
            raise RuntimeError(
                f"Expected one aggregate validation row, received {len(rows)}"
            )
        result = rows[0]

        failures: list[str] = []
        if result.row_count != EXPECTED_ROWS:
            failures.append(f"expected 48 rows, found {result.row_count}")
        if result.distinct_observation_count != EXPECTED_ROWS:
            failures.append(
                "expected 48 unique observation IDs, found "
                f"{result.distinct_observation_count}"
            )
        if result.missing_observed_at_count != 0:
            failures.append(
                f"found {result.missing_observed_at_count} rows without observed_at"
            )
        if failures:
            raise RuntimeError(
                f"BigQuery validation failed for batch {batch_id!r}: "
                + "; ".join(failures)
            )

        print(
            f"BigQuery validation passed for batch {batch_id}: "
            f"{result.row_count} rows, "
            f"{result.distinct_observation_count} unique observations, "
            "all observed_at values populated"
        )

    ingested_metadata = ingest_market_batch(generate_market_batch())
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            "dbt build --project-dir /opt/airflow/marketpulse/dbt "
            "--profiles-dir /opt/airflow/dbt-config --target dev "
            "--target-path /opt/airflow/marketpulse/data/dbt-target "
            "--select +marts.mart_market_signals"
        ),
        do_xcom_push=False,
    )
    ingested_metadata >> dbt_build

    validation = validate_bigquery_load(ingested_metadata)
    dbt_build >> validation


marketpulse_simulator_test()
