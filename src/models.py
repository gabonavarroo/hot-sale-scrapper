"""Data models for price tracking."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Source(str, Enum):
    """Price source."""

    BESTBUY = "bestbuy"
    APPLE_REFURBISHED = "apple_refurbished"


@dataclass
class Product:
    """Product with current price info."""

    source: Source
    name: str
    price: float
    url: str
    original_price: float | None = None
    raw_data: dict | None = None


@dataclass
class PriceRecord:
    """Historical price record for storage."""

    source: str
    product_name: str
    price: float
    url: str
    recorded_at: datetime
    original_price: float | None = None
