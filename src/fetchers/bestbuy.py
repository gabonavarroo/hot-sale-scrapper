"""Best Buy API client with optional scraping fallback."""

import logging
import os
import re
from urllib.parse import quote

import requests

from src.models import Product, Source

logger = logging.getLogger(__name__)

BESTBUY_API_BASE = "https://api.bestbuy.com/v1"
DEFAULT_SKU = "12110250"  # MacBook Pro 14" M4 Pro 24GB 512GB Space Black

# Full product URL (canonical format; may work better than short /site/-/SKU.p)
DEFAULT_PRODUCT_URL = (
    "https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-apple-m4-pro-chip-"
    "built-for-apple-intelligence-24gb-memory-512gb-ssd-space-black/JJGCQ8HVWL/sku/12110250"
)


def _bestbuy_product_url(sku: str) -> str:
    """Build Best Buy product page URL (env override or default)."""
    return os.environ.get(
        "BESTBUY_PRODUCT_URL",
        DEFAULT_PRODUCT_URL,
    )

# Price selectors to try (Best Buy may change structure)
PRICE_SELECTORS = [
    "[data-testid='customer-price']",
    ".priceView-customer-price span",
    ".priceView-customer-price",
    "[data-testid=customer-price]",
    "button[data-testid='customer-price']",
]


def _product_from_data(data: dict, sku: str) -> Product | None:
    """Build Product from API response."""
    sale_price = data.get("salePrice")
    if sale_price is None:
        return None
    name = data.get("name", "MacBook Pro 14\" M4 Pro")
    regular_price = data.get("regularPrice") or sale_price
    product_url = data.get("url", _bestbuy_product_url(sku))
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


def _fetch_bestbuy_via_requests(sku: str) -> Product | None:
    """
    Try to extract price from Best Buy page HTML with requests (no browser).
    Best Buy may embed JSON in script tags; requests avoids bot detection.
    """
    product_url = _bestbuy_product_url(sku)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(product_url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        logger.debug("Best Buy requests fetch failed: %s", e)
        return None

    # Look for embedded JSON: salePrice, currentPrice, customerPrice
    price_match = re.search(
        r'"(?:salePrice|currentPrice|customerPrice|price)["\s:]+([\d.]+)',
        html,
    )
    if price_match:
        try:
            price = float(price_match.group(1))
            if 100 < price < 10000:  # Sanity: MacBook range
                return Product(
                    source=Source.BESTBUY,
                    name="MacBook Pro 14\" M4 Pro 24GB 512GB Space Black",
                    price=price,
                    url=product_url,
                    original_price=None,
                    raw_data=None,
                )
        except ValueError:
            pass

    # Fallback: look for $X,XXX.XX pattern in HTML
    price_match = re.search(r'\$[\s]*([\d,]+\.?\d*)', html)
    if price_match:
        try:
            price = float(price_match.group(1).replace(",", ""))
            if 100 < price < 10000:
                return Product(
                    source=Source.BESTBUY,
                    name="MacBook Pro 14\" M4 Pro 24GB 512GB Space Black",
                    price=price,
                    url=product_url,
                    original_price=None,
                    raw_data=None,
                )
        except ValueError:
            pass

    return None


def _parse_price(text: str) -> float | None:
    """Extract numeric price from string like '$1,299.99' or '1299.99'."""
    if not text:
        return None
    match = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _fetch_bestbuy_via_scraping(sku: str) -> Product | None:
    """
    Scrape Best Buy product page with Playwright (no API key needed).

    Uses Firefox (less likely to be blocked by Best Buy/Akamai than Chromium).
    Returns Product or None on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed. Run: pip install playwright && playwright install firefox")
        return None

    product_url = _bestbuy_product_url(sku)
    name = "MacBook Pro 14\" M4 Pro 24GB 512GB Space Black"

    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            # "commit" = response received (faster than domcontentloaded; Best Buy can be slow)
            page.goto(product_url, wait_until="commit", timeout=60000)

            price_value: float | None = None
            for selector in PRICE_SELECTORS:
                try:
                    el = page.wait_for_selector(selector, timeout=15000)
                    if el:
                        text = el.inner_text()
                        price_value = _parse_price(text)
                        if price_value and price_value > 0:
                            break
                except Exception:
                    continue

            # Fallback: look for any element containing $ and digits
            if price_value is None:
                price_els = page.query_selector_all("[class*='price']")
                for el in price_els:
                    text = el.inner_text()
                    p = _parse_price(text)
                    if p and 100 < p < 5000:  # Sanity check for MacBook price range
                        price_value = p
                        break

            browser.close()

        if price_value is None or price_value <= 0:
            logger.warning("Best Buy scraping: could not extract price from page")
            return None

        return Product(
            source=Source.BESTBUY,
            name=name,
            price=price_value,
            url=product_url,
            original_price=None,
            raw_data=None,
        )
    except Exception as e:
        logger.warning("Best Buy scraping failed: %s", e)
        return None


def _use_scraping_fallback() -> bool:
    """Check if scraping fallback is enabled via BESTBUY_USE_SCRAPING."""
    val = os.environ.get("BESTBUY_USE_SCRAPING", "false").lower()
    return val in ("true", "1", "yes")


def fetch_bestbuy_product() -> Product | None:
    """
    Fetch MacBook Pro 14" M4 Pro product from Best Buy.

    Order: 1) API (if BESTBUY_API_KEY), 2) API search fallback on 404,
    3) Playwright scraping (if BESTBUY_USE_SCRAPING=true and API failed or no key).
    """
    sku = os.environ.get("BESTBUY_SKU", DEFAULT_SKU)
    api_key = os.environ.get("BESTBUY_API_KEY")

    # 1. Try API if key present
    if api_key:
        url = f"{BESTBUY_API_BASE}/products/{sku}.json"
        params = {
            "apiKey": api_key,
            "show": "name,salePrice,regularPrice,url",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 404:
                logger.warning("Best Buy SKU %s not found (404). Trying search fallback.", sku)
                result = _search_product(api_key)
                if result:
                    return result
            else:
                resp.raise_for_status()
                data = resp.json()
                return _product_from_data(data, sku)
        except requests.RequestException as e:
            logger.warning("Best Buy API error: %s", e)

    # 2. Scraping fallback when enabled (requests only; Playwright often blocked by Best Buy)
    if _use_scraping_fallback():
        logger.info("Best Buy: trying requests fallback (no API key or API failed)")
        return _fetch_bestbuy_via_requests(sku)

    return None
