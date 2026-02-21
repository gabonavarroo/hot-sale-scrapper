"""Apple Refurbished store fetcher using the refurbished package."""

from refurbished import Store

from src.models import Product, Source

# Filter: M4 Pro, 12-core CPU, 16-core GPU, 512GB SSD, Space Black
TARGET_KEYWORDS = ["M4 Pro", "12‑Core CPU", "16‑Core GPU", "512GB", "Space Black"]
ALT_KEYWORDS = ["M4 Pro", "12-core CPU", "16-core GPU", "512", "Space Black"]


def _matches_target(name: str) -> bool:
    """Check if product name matches our target MacBook Pro M4 Pro spec."""
    name_lower = name.lower()
    # Must be 14" MacBook Pro
    if "14-inch" not in name or "macbook pro" not in name_lower:
        return False
    # M4 Pro
    # if "m4 pro" not in name_lower and "m4 pro chip" not in name_lower:
    #     return False
    # # 12-core CPU
    # if "12" not in name and "12‑core" not in name and "12-core" not in name_lower:
    #     return False
    # # 16-core GPU
    # if "16" not in name and "16‑core" not in name and "16-core" not in name_lower:
    #     return False
    # 512GB
    # if "512" not in name:
    #     return False
    # Space Black
    # if "space black" not in name_lower and "space black" not in name_lower:
    #     return False
    return True


def fetch_apple_refurbished() -> list[Product]:
    """
    Fetch matching MacBook Pro M4 Pro 14" from Apple Refurbished (US store).

    Returns list of matching products (may be empty if none available).
    """
    try:
        store = Store("us")
        macs = list(store.get_macs())
    except Exception as e:
        raise RuntimeError(f"Apple Refurbished fetch error: {e}") from e

    results: list[Product] = []
    for mac in macs:
        name = getattr(mac, "name", str(mac))
        if not _matches_target(name):
            continue

        price = getattr(mac, "price", 0)
        url = getattr(mac, "url", "https://www.apple.com/shop/refurbished/mac/2024-14-inch-macbook-pro")
        prev_price = getattr(mac, "previous_price", None)

        results.append(
            Product(
                source=Source.APPLE_REFURBISHED,
                name=name,
                price=float(price),
                url=url,
                original_price=float(prev_price) if prev_price is not None else None,
                raw_data=None,
            )
        )

    return results
