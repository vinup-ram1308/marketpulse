"""Tests for the local timestamp-keyed market simulator."""

from datetime import datetime, timedelta, timezone
import hashlib

import pandas as pd
import pytest

from simulator.market_simulator import (
    REQUIRED_COLUMNS,
    STOCK_STATUSES,
    MarketSimulator,
    SimulationParameters,
)


@pytest.fixture
def fixed_start() -> datetime:
    """Return a stable UTC instant for deterministic batch tests."""
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _assert_same_market_snapshot(
    first: pd.DataFrame, second: pd.DataFrame
) -> None:
    pd.testing.assert_frame_equal(
        first.drop(columns="batch_id"),
        second.drop(columns="batch_id"),
    )


def test_load_catalogs() -> None:
    simulator = MarketSimulator(seed=1)

    products, competitors = simulator.load_catalogs()

    assert len(products) == 12
    assert len(competitors) == 4
    assert {"product_id", "base_price", "currency"}.issubset(products.columns)
    assert {"competitor_id", "competitor_name", "market"}.issubset(competitors.columns)
    assert set(products["category"]) == {
        "Smartphones",
        "Laptops",
        "Headphones and Audio",
    }


def test_batch_contains_every_product_competitor_pair(fixed_start: datetime) -> None:
    simulator = MarketSimulator(seed=2)
    products, competitors = simulator.load_catalogs()

    observations = simulator.generate_batch(fixed_start)
    expected_pairs = {
        (product_id, competitor_id)
        for product_id in products["product_id"]
        for competitor_id in competitors["competitor_id"]
    }
    actual_pairs = set(zip(observations["product_id"], observations["competitor_id"]))

    assert len(observations) == len(products) * len(competitors)
    assert actual_pairs == expected_pairs


def test_observation_ids_are_deterministic(fixed_start: datetime) -> None:
    first = MarketSimulator(seed=3).generate_batch(fixed_start)
    second = MarketSimulator(seed=99).generate_batch(fixed_start)

    assert first["observation_id"].tolist() == second["observation_id"].tolist()
    row = first.iloc[0]
    identity = f"{row['product_id']}|{row['competitor_id']}|{fixed_start.isoformat(timespec='microseconds')}"
    assert row["observation_id"] == hashlib.sha256(identity.encode()).hexdigest()


def test_same_seed_and_start_produce_identical_multi_batch_snapshots(
    fixed_start: datetime,
) -> None:
    first = MarketSimulator(seed=15).generate_batches(4, fixed_start)
    second = MarketSimulator(seed=15).generate_batches(4, fixed_start)

    for first_batch, second_batch in zip(first, second):
        _assert_same_market_snapshot(first_batch, second_batch)
    assert len({batch["batch_id"].iloc[0] for batch in first}) == len(first)
    assert len({batch["batch_id"].iloc[0] for batch in second}) == len(second)


def test_same_timestamp_replays_on_one_instance(fixed_start: datetime) -> None:
    simulator = MarketSimulator(seed=42)

    first = simulator.generate_batch(fixed_start)
    replay = simulator.generate_batch(fixed_start)

    _assert_same_market_snapshot(first, replay)


def test_same_seed_and_timestamp_replay_across_instances(
    fixed_start: datetime,
) -> None:
    first = MarketSimulator(seed=42).generate_batch(fixed_start)
    second = MarketSimulator(seed=42).generate_batch(fixed_start)

    _assert_same_market_snapshot(first, second)


def test_equivalent_timezone_instants_produce_identical_snapshots(
    fixed_start: datetime,
) -> None:
    equivalent_instant = datetime(
        2026, 1, 1, 5, tzinfo=timezone(timedelta(hours=5))
    )

    first = MarketSimulator(seed=42).generate_batch(fixed_start)
    second = MarketSimulator(seed=42).generate_batch(equivalent_instant)

    _assert_same_market_snapshot(first, second)
    assert first["observed_at"].tolist() == second["observed_at"].tolist()


def test_naive_timestamp_is_treated_as_utc(fixed_start: datetime) -> None:
    naive_timestamp = fixed_start.replace(tzinfo=None)

    aware = MarketSimulator(seed=42).generate_batch(fixed_start)
    naive = MarketSimulator(seed=42).generate_batch(naive_timestamp)

    _assert_same_market_snapshot(aware, naive)


def test_market_conditions_vary_across_representative_timestamps(
    fixed_start: datetime,
) -> None:
    observations = pd.concat(
        MarketSimulator(seed=42).generate_batches(24, fixed_start),
        ignore_index=True,
    )

    assert observations["price"].nunique() > 1
    assert observations["stock_status"].nunique() > 1
    assert observations["stock_quantity"].nunique() > 1
    assert observations["promotion_flag"].nunique() > 1
    assert observations["promotion_pct"].nunique() > 1


def test_observation_ids_change_for_same_pair_at_different_timestamps(
    fixed_start: datetime,
) -> None:
    first, second = MarketSimulator(seed=16).generate_batches(2, fixed_start)
    pair = (first.iloc[0]["product_id"], first.iloc[0]["competitor_id"])
    first_observation = first.loc[
        (first["product_id"] == pair[0]) & (first["competitor_id"] == pair[1])
    ].iloc[0]
    second_observation = second.loc[
        (second["product_id"] == pair[0]) & (second["competitor_id"] == pair[1])
    ].iloc[0]

    assert first_observation["observed_at"] != second_observation["observed_at"]
    assert first_observation["observation_id"] != second_observation["observation_id"]


def test_prices_remain_within_sensible_bounds(fixed_start: datetime) -> None:
    simulator = MarketSimulator(seed=4)
    products, _ = simulator.load_catalogs()
    observations = pd.concat(
        simulator.generate_batches(10, fixed_start), ignore_index=True
    )
    base_prices = products.set_index("product_id")["base_price"]
    expected_base = observations["product_id"].map(base_prices)

    assert (observations["price"] >= expected_base * 0.5).all()
    assert (observations["price"] <= expected_base * 2.0).all()


def test_inventory_and_promotions_are_valid(fixed_start: datetime) -> None:
    observations = MarketSimulator(seed=5).generate_batch(fixed_start)

    assert set(observations["stock_status"]).issubset(STOCK_STATUSES)
    assert (observations["stock_quantity"] >= 0).all()
    assert observations.loc[
        observations["stock_status"] == "OUT_OF_STOCK", "stock_quantity"
    ].eq(0).all()
    assert observations["promotion_pct"].between(0, 100).all()
    assert observations.loc[~observations["promotion_flag"], "promotion_pct"].eq(0).all()


def test_multiple_batches_have_increasing_timestamps(fixed_start: datetime) -> None:
    simulator = MarketSimulator(seed=6)

    batches = simulator.generate_batches(4, fixed_start)

    timestamps = [batch["observed_at"].iloc[0] for batch in batches]
    assert timestamps == sorted(timestamps)
    assert all(
        later - earlier == timedelta(hours=1)
        for earlier, later in zip(timestamps, timestamps[1:])
    )


def test_promotion_probability_applies_to_each_independent_snapshot(
    fixed_start: datetime,
) -> None:
    simulator = MarketSimulator(
        seed=7,
        parameters=SimulationParameters(promotion_probability=1.0),
    )

    first, second = simulator.generate_batches(2, fixed_start)

    assert first["promotion_flag"].all()
    assert second["promotion_flag"].all()
    assert first["promotion_pct"].gt(0).all()
    assert second["promotion_pct"].gt(0).all()


def test_generation_order_does_not_affect_a_timestamp(fixed_start: datetime) -> None:
    later = fixed_start + timedelta(hours=4)

    first_simulator = MarketSimulator(seed=42)
    first_simulator.generate_batch(fixed_start)
    first_order_result = first_simulator.generate_batch(later)

    second_simulator = MarketSimulator(seed=42)
    second_simulator.generate_batch(later)
    second_simulator.generate_batch(fixed_start)
    second_order_result = second_simulator.generate_batch(later)
    isolated_result = MarketSimulator(seed=42).generate_batch(later)

    _assert_same_market_snapshot(first_order_result, isolated_result)
    _assert_same_market_snapshot(second_order_result, isolated_result)


@pytest.mark.parametrize("invalid_price", [float("nan"), float("inf"), -float("inf")])
def test_validation_rejects_non_finite_prices(
    fixed_start: datetime, invalid_price: float
) -> None:
    observations = MarketSimulator(seed=11).generate_batch(fixed_start)
    observations.loc[observations.index[0], "price"] = invalid_price

    with pytest.raises(ValueError, match="prices must be finite"):
        MarketSimulator._validate_observations(observations)


@pytest.mark.parametrize(
    ("status", "quantity", "message"),
    [
        ("OUT_OF_STOCK", 1, "OUT_OF_STOCK.*quantity 0"),
        ("LOW_STOCK", 0, "LOW_STOCK.*positive quantity"),
        ("IN_STOCK", 10, "IN_STOCK.*exceed the LOW_STOCK range"),
    ],
)
def test_validation_enforces_stock_quantity_by_status(
    fixed_start: datetime, status: str, quantity: int, message: str
) -> None:
    observations = MarketSimulator(seed=12).generate_batch(fixed_start)
    observations.loc[observations.index[0], "stock_status"] = status
    observations.loc[observations.index[0], "stock_quantity"] = quantity

    with pytest.raises(ValueError, match=message):
        MarketSimulator._validate_observations(observations)


@pytest.mark.parametrize(
    ("promotion_flag", "promotion_pct", "message"),
    [
        (False, 5.0, "without promotions.*promotion_pct 0"),
        (True, 0.0, "with promotions.*positive promotion_pct"),
    ],
)
def test_validation_enforces_promotion_consistency(
    fixed_start: datetime,
    promotion_flag: bool,
    promotion_pct: float,
    message: str,
) -> None:
    observations = MarketSimulator(seed=13).generate_batch(fixed_start)
    observations.loc[observations.index[0], "promotion_flag"] = promotion_flag
    observations.loc[observations.index[0], "promotion_pct"] = promotion_pct

    with pytest.raises(ValueError, match=message):
        MarketSimulator._validate_observations(observations)


def test_validation_rejects_duplicate_observation_ids(fixed_start: datetime) -> None:
    observations = MarketSimulator(seed=14).generate_batch(fixed_start)
    observations.loc[observations.index[1], "observation_id"] = observations.loc[
        observations.index[0], "observation_id"
    ]

    with pytest.raises(ValueError, match="duplicate observation_id"):
        MarketSimulator._validate_observations(observations)


def test_generated_dataframe_has_required_columns(fixed_start: datetime) -> None:
    observations = MarketSimulator(seed=8).generate_batch(fixed_start)

    assert tuple(observations.columns) == REQUIRED_COLUMNS
    assert observations["observed_at"].notna().all()
    assert observations["observed_at"].map(lambda value: value.utcoffset() == timedelta(0)).all()


def test_invalid_price_probabilities_are_rejected() -> None:
    with pytest.raises(ValueError, match="must sum to 1"):
        SimulationParameters(normal_probability=0.5)