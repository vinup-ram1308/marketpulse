"""Generate reproducible market snapshots from local catalogs."""

from __future__ import annotations

import argparse
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd


REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "observation_id",
    "batch_id",
    "product_id",
    "product_name",
    "category",
    "brand",
    "competitor_id",
    "competitor_name",
    "market",
    "observed_at",
    "price",
    "currency",
    "stock_status",
    "stock_quantity",
    "promotion_flag",
    "promotion_pct",
    "source",
)
STOCK_STATUSES: Final[tuple[str, ...]] = (
    "IN_STOCK",
    "LOW_STOCK",
    "OUT_OF_STOCK",
)
SOURCE: Final[str] = "market_simulator"
LOW_STOCK_MAX: Final[int] = 10
IN_STOCK_MIN: Final[int] = LOW_STOCK_MAX + 2


@dataclass(frozen=True)
class SimulationParameters:
    """Snapshot settings and consecutive-batch spacing.

    Cross-batch transition settings remain accepted for API compatibility but do
    not affect independently generated snapshots.
    """

    batch_interval: timedelta = timedelta(hours=1)
    promotion_probability: float = 0.18
    promotion_end_probability: float = 0.4
    stock_transition_probability: float = 0.16
    demand_probability: float = 0.7
    demand_quantity_min: int = 1
    demand_quantity_max: int = 8
    replenishment_probability: float = 0.2
    replenishment_quantity_min: int = 5
    replenishment_quantity_max: int = 30
    normal_probability: float = 0.78
    drop_probability: float = 0.1
    rise_probability: float = 0.1
    shock_probability: float = 0.02
    normal_change_std: float = 0.015
    minimum_price_multiplier: float = 0.5
    maximum_price_multiplier: float = 2.0

    def __post_init__(self) -> None:
        """Reject settings that could make transitions or prices invalid."""
        probability_values = (
            self.promotion_probability,
            self.promotion_end_probability,
            self.stock_transition_probability,
            self.demand_probability,
            self.replenishment_probability,
            self.normal_probability,
            self.drop_probability,
            self.rise_probability,
            self.shock_probability,
        )
        if any(not 0 <= value <= 1 for value in probability_values):
            raise ValueError("All probabilities must be between 0 and 1")
        if not np.isclose(
            self.normal_probability
            + self.drop_probability
            + self.rise_probability
            + self.shock_probability,
            1.0,
        ):
            raise ValueError("Price event probabilities must sum to 1")
        if self.batch_interval <= timedelta(0):
            raise ValueError("batch_interval must be greater than zero")
        if self.normal_change_std < 0:
            raise ValueError("normal_change_std cannot be negative")
        quantity_ranges = (
            (self.demand_quantity_min, self.demand_quantity_max),
            (self.replenishment_quantity_min, self.replenishment_quantity_max),
        )
        if any(minimum < 1 or maximum < minimum for minimum, maximum in quantity_ranges):
            raise ValueError("Demand and replenishment quantities must be positive and ordered")
        if not 0 < self.minimum_price_multiplier < self.maximum_price_multiplier:
            raise ValueError("Price multipliers must be positive and ordered")


@dataclass(frozen=True)
class _PairState:
    """Generated market fields for one product and competitor pair."""

    price: float
    stock_status: str
    stock_quantity: int
    promotion_flag: bool
    promotion_pct: float


class MarketSimulator:
    """Generate deterministic, timestamp-keyed market snapshots."""

    def __init__(
        self,
        seed: int | None = None,
        parameters: SimulationParameters | None = None,
        catalog_dir: str | Path | None = None,
    ) -> None:
        self.parameters = parameters or SimulationParameters()
        self._seed = seed
        self._catalog_dir = Path(catalog_dir) if catalog_dir else Path(__file__).parent
        self._products: pd.DataFrame | None = None
        self._competitors: pd.DataFrame | None = None

    def load_catalogs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load and validate the product and competitor CSV catalogs."""
        products = pd.read_csv(self._catalog_dir / "product_catalog.csv")
        competitors = pd.read_csv(self._catalog_dir / "competitor_catalog.csv")
        self._validate_catalog(
            products,
            ("product_id", "product_name", "category", "brand", "base_price", "currency"),
            "product",
        )
        self._validate_catalog(
            competitors,
            ("competitor_id", "competitor_name", "market"),
            "competitor",
        )
        if (products["base_price"] <= 0).any():
            raise ValueError("Product base_price values must be positive")
        self._products = products
        self._competitors = competitors
        return products.copy(), competitors.copy()

    @staticmethod
    def _validate_catalog(
        catalog: pd.DataFrame, columns: tuple[str, ...], catalog_name: str
    ) -> None:
        missing = [column for column in columns if column not in catalog.columns]
        if missing:
            raise ValueError(f"{catalog_name} catalog is missing columns: {missing}")
        if catalog.empty or catalog[list(columns)].isna().any().any():
            raise ValueError(f"{catalog_name} catalog must contain complete rows")
        id_column = columns[0]
        if catalog[id_column].duplicated().any():
            raise ValueError(f"{catalog_name} catalog contains duplicate {id_column}s")

    def generate_batch(self, observed_at: datetime | None = None) -> pd.DataFrame:
        """Generate one deterministic observation per pair for the requested instant.

        Replaying an instant produces the same market fields regardless of prior calls.
        """
        products, competitors = self._get_catalogs()
        timestamp = self._next_timestamp(observed_at)
        rng = self._rng_for_timestamp(timestamp)
        batch_id = str(uuid.uuid4())
        rows: list[dict[str, object]] = []

        for _, product in products.iterrows():
            for competitor_index, competitor in competitors.iterrows():
                product_id = str(product["product_id"])
                competitor_id = str(competitor["competitor_id"])
                base_price = float(product["base_price"])
                state = self._snapshot_state(
                    base_price, competitor_index, rng
                )
                rows.append(
                    {
                        "observation_id": self._make_observation_id(
                            product_id, competitor_id, timestamp
                        ),
                        "batch_id": batch_id,
                        "product_id": product_id,
                        "product_name": str(product["product_name"]),
                        "category": str(product["category"]),
                        "brand": str(product["brand"]),
                        "competitor_id": competitor_id,
                        "competitor_name": str(competitor["competitor_name"]),
                        "market": str(competitor["market"]),
                        "observed_at": timestamp,
                        "price": round(state.price, 2),
                        "currency": str(product["currency"]),
                        "stock_status": state.stock_status,
                        "stock_quantity": state.stock_quantity,
                        "promotion_flag": state.promotion_flag,
                        "promotion_pct": state.promotion_pct,
                        "source": SOURCE,
                    }
                )

        observations = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
        self._validate_observations(observations)
        return observations

    def generate_batches(
        self, count: int, start_at: datetime | None = None
    ) -> list[pd.DataFrame]:
        """Generate multiple consecutive batches, optionally from a fixed UTC time."""
        if count < 0:
            raise ValueError("count cannot be negative")
        batches: list[pd.DataFrame] = []
        timestamp = self._next_timestamp(start_at)
        for _ in range(count):
            batches.append(self.generate_batch(timestamp))
            timestamp += self.parameters.batch_interval
        return batches

    def _get_catalogs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self._products is None or self._competitors is None:
            self.load_catalogs()
        assert self._products is not None and self._competitors is not None
        return self._products, self._competitors

    def _next_timestamp(self, requested: datetime | None) -> datetime:
        """Normalize a requested instant, preserving the existing naive-time rule."""
        if requested is None:
            return datetime.now(timezone.utc)
        return self._as_utc(requested)

    def _rng_for_timestamp(self, timestamp: datetime) -> np.random.Generator:
        """Derive a stable random stream from the configured seed and UTC instant."""
        canonical_timestamp = self._as_utc(timestamp).isoformat(
            timespec="microseconds"
        )
        seed_material = (
            f"marketpulse-simulator-v1\0{self._seed!r}\0{canonical_timestamp}"
        ).encode("utf-8")
        digest = hashlib.sha256(seed_material).digest()
        return np.random.default_rng(int.from_bytes(digest, byteorder="big"))

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _snapshot_state(
        self,
        base_price: float,
        competitor_index: int,
        rng: np.random.Generator,
    ) -> _PairState:
        """Sample one pair's market fields without consulting prior batches."""
        competitor_factor = 0.94 + competitor_index * 0.04
        price = base_price * competitor_factor * rng.uniform(0.97, 1.03)
        stock_status = str(rng.choice(STOCK_STATUSES, p=(0.78, 0.18, 0.04)))
        promotion_flag = bool(
            rng.random() < self.parameters.promotion_probability
        )
        promotion_pct = self._new_promotion_pct(rng) if promotion_flag else 0.0
        quantity = self._stock_quantity(stock_status, rng)
        bounded_price = min(
            base_price * self.parameters.maximum_price_multiplier,
            max(base_price * self.parameters.minimum_price_multiplier, price),
        )
        return _PairState(
            price=bounded_price,
            stock_status=stock_status,
            stock_quantity=quantity,
            promotion_flag=promotion_flag,
            promotion_pct=promotion_pct,
        )

    def _stock_quantity(self, status: str, rng: np.random.Generator) -> int:
        if status == "OUT_OF_STOCK":
            return 0
        if status == "LOW_STOCK":
            return int(rng.integers(1, LOW_STOCK_MAX + 1))
        return int(rng.integers(12, 181))

    def _new_promotion_pct(self, rng: np.random.Generator) -> float:
        return round(float(rng.uniform(5, 35)), 2)

    @staticmethod
    def _make_observation_id(
        product_id: str, competitor_id: str, timestamp: datetime
    ) -> str:
        canonical_timestamp = timestamp.astimezone(timezone.utc).isoformat(
            timespec="microseconds"
        )
        identity = f"{product_id}|{competitor_id}|{canonical_timestamp}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_observations(observations: pd.DataFrame) -> None:
        missing = [column for column in REQUIRED_COLUMNS if column not in observations]
        if missing:
            raise ValueError(f"Generated observations are missing columns: {missing}")
        if observations.empty or observations["observed_at"].isna().any():
            raise ValueError("Generated observations must include timestamps")
        prices = pd.to_numeric(observations["price"], errors="coerce")
        if not np.isfinite(prices.to_numpy(dtype=float)).all():
            raise ValueError("Generated prices must be finite numbers")
        if (prices < 0).any():
            raise ValueError("Generated prices cannot be negative")
        if not observations["stock_status"].isin(STOCK_STATUSES).all():
            raise ValueError("Generated stock status is invalid")
        if (observations["stock_quantity"] < 0).any():
            raise ValueError("Generated stock quantity cannot be negative")
        out_of_stock = observations["stock_status"] == "OUT_OF_STOCK"
        low_stock = observations["stock_status"] == "LOW_STOCK"
        in_stock = observations["stock_status"] == "IN_STOCK"
        if not observations.loc[out_of_stock, "stock_quantity"].eq(0).all():
            raise ValueError("OUT_OF_STOCK observations must have quantity 0")
        if not observations.loc[low_stock, "stock_quantity"].gt(0).all():
            raise ValueError("LOW_STOCK observations must have positive quantity")
        if not observations.loc[in_stock, "stock_quantity"].gt(LOW_STOCK_MAX).all():
            raise ValueError("IN_STOCK observations must exceed the LOW_STOCK range")
        if not observations["promotion_pct"].between(0, 100).all():
            raise ValueError("Generated promotion percentage must be between 0 and 100")
        if not observations.loc[~observations["promotion_flag"], "promotion_pct"].eq(0).all():
            raise ValueError("Observations without promotions must have promotion_pct 0")
        if not observations.loc[observations["promotion_flag"], "promotion_pct"].gt(0).all():
            raise ValueError("Observations with promotions must have positive promotion_pct")
        if observations["observation_id"].duplicated().any():
            raise ValueError("Generated observations contain duplicate observation_id values")
        if not observations["observed_at"].map(
            lambda value: value.tzinfo is not None and value.utcoffset() == timedelta(0)
        ).all():
            raise ValueError("Generated timestamps must be UTC-aware")


def main() -> int:
    """Run the simulator CLI and print a concise batch summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=1, help="number of batches to generate")
    parser.add_argument("--seed", type=int, default=None, help="reproducible random seed")
    args = parser.parse_args()
    if args.batches < 1:
        parser.error("--batches must be at least 1")

    simulator = MarketSimulator(seed=args.seed)
    products, competitors = simulator.load_catalogs()
    batches = simulator.generate_batches(args.batches)
    observations = pd.concat(batches, ignore_index=True)
    print(f"Products: {len(products)} | Competitors: {len(competitors)}")
    print(f"Batches: {len(batches)} | Observations: {len(observations)}")
    print(f"Average price: {observations['price'].mean():.2f}")
    print("Stock status counts:")
    print(observations["stock_status"].value_counts().sort_index().to_string())
    print("Sample observations:")
    print(observations.head().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())