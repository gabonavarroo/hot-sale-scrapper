"""Price comparison and threshold logic."""

from datetime import datetime

from src.models import PriceRecord, Product, Source
from src.storage import get_last_price, save_price


def get_target_price() -> float:
    """Get target price threshold from environment."""
    import os

    val = os.environ.get("TARGET_PRICE_USD", "0")
    try:
        return float(val)
    except ValueError:
        return 0.0


def should_alert(product: Product, target_price: float) -> bool:
    """
    Return True if product price is at or below target threshold.
    Target 0 means disabled (no alerts).
    """
    if target_price <= 0:
        return False
    return product.price <= target_price


def record_and_check(product: Product, target_price: float) -> tuple[bool, bool]:
    """
    Save price to history and determine if we should alert.

    Returns (should_alert, is_new_low).
    """
    now = datetime.utcnow()
    previous_price = get_last_price(product.source, product.name)

    record = PriceRecord(
        source=product.source.value,
        product_name=product.name,
        price=product.price,
        url=product.url,
        recorded_at=now,
        original_price=product.original_price,
    )
    save_price(record)

    alert = should_alert(product, target_price)
    is_new_low = previous_price is None or product.price < previous_price

    return alert, is_new_low
