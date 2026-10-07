"""Backfill deterministic MarketPulse observations for an arbitrary time window.

Example:
    python scripts/backfill_market_history.py \
        --start "2026-10-06T00:00:00Z" \
        --hours 46

The script generates one simulator batch per hour and ingests each batch
through the existing ingestion pipeline.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ingestion.pipeline import ingest_batch
from simulator.market_simulator import MarketSimulator


EXPECTED_ROWS_PER_BATCH = 48


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""
    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    timestamp = datetime.fromisoformat(normalized)

    if timestamp.tzinfo is None:
        raise ValueError(
            "Start timestamp must include a timezone, for example "
            "'2026-10-06T00:00:00Z'."
        )

    return timestamp.astimezone(timezone.utc)


def backfill(
    start_at: datetime,
    hours: int,
    seed: int,
) -> None:
    """Generate and ingest one deterministic batch per hour."""
    simulator = MarketSimulator(seed=seed)

    print("=" * 72)
    print("MarketPulse historical backfill")
    print("=" * 72)
    print(f"Start:  {start_at.isoformat()}")
    print(f"Hours:  {hours}")
    print(f"End:    {(start_at + timedelta(hours=hours - 1)).isoformat()}")
    print(f"Seed:   {seed}")
    print(f"Rows:   {hours * EXPECTED_ROWS_PER_BATCH:,}")
    print("=" * 72)

    total_rows = 0

    for index in range(hours):
        observed_at = start_at + timedelta(hours=index)

        observations = simulator.generate_batch(observed_at)

        if len(observations) != EXPECTED_ROWS_PER_BATCH:
            raise ValueError(
                f"Expected {EXPECTED_ROWS_PER_BATCH} observations at "
                f"{observed_at.isoformat()}, received {len(observations)}"
            )

        result = ingest_batch(observations)

        if result.rows_loaded != EXPECTED_ROWS_PER_BATCH:
            raise RuntimeError(
                f"Unexpected loaded row count at "
                f"{observed_at.isoformat()}: "
                f"{result.rows_loaded}"
            )

        total_rows += result.rows_loaded

        print(
            f"[{index + 1:03d}/{hours:03d}] "
            f"{observed_at.isoformat()} → "
            f"{result.rows_loaded} rows | "
            f"batch_id={result.batch_id}"
        )

    print("=" * 72)
    print(f"Backfill complete: {total_rows:,} observations loaded")
    print("=" * 72)


def main() -> int:
    """Parse CLI arguments and execute the backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill deterministic MarketPulse observations."
    )

    parser.add_argument(
        "--start",
        required=True,
        help=(
            "UTC start timestamp in ISO-8601 format, "
            "for example 2026-10-06T00:00:00Z"
        ),
    )

    parser.add_argument(
        "--hours",
        type=int,
        required=True,
        help="Number of hourly observations to generate.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Simulator seed used for deterministic market conditions.",
    )

    args = parser.parse_args()

    if args.hours < 1:
        parser.error("--hours must be at least 1")

    try:
        start_at = parse_timestamp(args.start)
    except ValueError as error:
        parser.error(str(error))

    backfill(
        start_at=start_at,
        hours=args.hours,
        seed=args.seed,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())