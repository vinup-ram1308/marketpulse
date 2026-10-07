"""Pydantic response models for the MarketPulse API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


SignalType = Literal[
    "PRICE_MOVEMENT",
    "PROMOTION_SURGE",
    "INVENTORY_PRESSURE",
    "PRICE_DISPERSION",
]
Severity = Literal["LOW", "MEDIUM", "HIGH"]


class HealthResponse(BaseModel):
    """Health-check response."""

    status: Literal["ok"]
    service: Literal["marketpulse-api"]


class ProductResponse(BaseModel):
    """Distinct product dimension available in market snapshots."""

    product_id: str
    product_name: str
    category: str
    brand: str


class MarketSignalResponse(BaseModel):
    """Aggregated competitor market metrics for one snapshot."""

    product_id: str
    product_name: str
    category: str
    brand: str
    market: str
    currency: str
    observed_at: datetime
    competitor_count: int
    avg_competitor_price: float
    min_competitor_price: float
    max_competitor_price: float
    price_spread: float
    price_spread_pct: float
    lowest_competitor_name: str
    lowest_competitor_price: float
    highest_competitor_name: str
    highest_competitor_price: float
    in_stock_pct: float
    promotion_competitor_pct: float
    market_price_pressure: float
    promotion_activity_flag: bool


class AlertResponse(BaseModel):
    """One detected temporal market alert."""

    product_id: str
    product_name: str
    market: str
    currency: str
    observed_at: datetime
    signal_type: SignalType
    severity: Severity
    message: str


class AlertCountResponse(BaseModel):
    """Alert count for one signal type and severity pair."""

    signal_type: SignalType
    severity: Severity
    alert_count: int


class AlertSummaryResponse(BaseModel):
    """Aggregated alert counts and overall total."""

    total_alerts: int
    counts: list[AlertCountResponse]
