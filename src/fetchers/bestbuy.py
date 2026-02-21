"""Best Buy API client."""

import logging
import os
from urllib.parse import quote

import requests

from src.models import Product, Source

logger = logging.getLogger(__name__)

BESTBUY_API_BASE = "https://api.bestbuy.com/v1"
DEFAULT_SKU = "12110250"  # MacBook Pro 14" M4 Pro 24GB 512GB Space Black


def _product_from_data(data: dict, sku: str) -> Product | None:
    """Build Product from API response."""
    sale_price = data.get("salePrice")
    if sale_price is None:
        return None
    name = data.get("name", "MacBook Pro 14\" M4 Pro")
    regular_price = data.get("regularPrice") or sale_price
    product_url = data.get("url", f"https://www.bestbuy.com/site/-/{sku}.p")
    return Product(
        source=Source.BESTBUY,
        name=name,
        price=float(sale_price),
        url=product_url,
        original_price=float(regular_price) if regular_price else None,
        raw_data=data,
    )


def _matches_target(name: str) -> bool:
    """Check if product matches MacBook Pro 14\" M4 Pro 24GB 512GB Space Black."""
    n = name.lower()
    return (
        "m4 pro" in n
        and "14" in n
        and "24" in name  # 24GB
        and "512" in name
        and "space black" in n
    )


def _search_product(api_key: str) -> Product | None:
    """Search for MacBook Pro 14\" M4 Pro 24GB 512GB when SKU lookup fails."""
    # Best Buy API: wildcard only at end. Search all Apple MacBooks, filter in code.
    query = "manufacturer=Apple&name=MacBook*"
    url = f"{BESTBUY_API_BASE}/products({quote(query, safe='*=&')})"
    params = {
        "apiKey": api_key,
        "format": "json",
        "show": "sku,name,salePrice,regularPrice,url",
        "pageSize": 100,
    }
    for page in range(5):  # Check first 500 results
        params["page"] = page + 1
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug("Best Buy search fallback failed (page %d): %s", page + 1, e)
            return None

        products = data.get("products", [])
        for p in products:
            name = p.get("name") or ""
            if _matches_target(name):
                return _product_from_data(p, str(p.get("sku", "")))

        if page + 1 >= data.get("totalPages", 1):
            break
    return None


def fetch_bestbuy_product() -> Product | None:
    """
    Fetch MacBook Pro 14" M4 Pro product from Best Buy API.

    Tries direct SKU first (configurable via BESTBUY_SKU). On 404, falls back to search.
    Returns Product or None if API key missing or product not found.
    """
    api_key = os.environ.get("BESTBUY_API_KEY")
    if not api_key:
        return None

    sku = os.environ.get("BESTBUY_SKU", DEFAULT_SKU)
    url = f"{BESTBUY_API_BASE}/products/{sku}.json"
    params = {
        "apiKey": api_key,
        "show": "name,salePrice,regularPrice,url",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 404:
            logger.warning(
                "Best Buy SKU %s not found (404). Product may be discontinued. Trying search fallback.",
                sku,
            )
            return _search_product(api_key)
        resp.raise_for_status()
        data = resp.json()
        return _product_from_data(data, sku)
    except requests.RequestException as e:
        raise RuntimeError(f"Best Buy API error: {e}") from e
