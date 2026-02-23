"""
Best Buy price fetcher.

Capa 0 — API oficial (api.bestbuy.com)
    Requiere BESTBUY_API_KEY. Devuelve el MSRP ($1,999), NO descuentos
    temporales de Apple por acuerdo MAP. Útil solo para disponibilidad.

Capa 1 — curl_cffi + página de producto (PRINCIPAL)
    Imita el TLS fingerprint de Chrome a nivel de sistema operativo,
    bypasseando la detección de Akamai Bot Manager que bloqueaba requests
    y Camoufox. Extrae el precio real con descuento del HTML embebido.

Capa 2 — curl_cffi + Falcor/priceBlocks
    Endpoints JSON internos de Best Buy con sesión curl_cffi.
"""

import json
import logging
import os
import random
import re
import time

import requests  # Solo para la API oficial (no afectada por Akamai)

from src.models import Product, Source

logger = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

DEFAULT_SKU = "6602748"
DEFAULT_PRODUCT_URL = (
    "https://www.bestbuy.com/product/"
    "apple-macbook-pro-14-inch-laptop-apple-m4-pro-chip-"
    "built-for-apple-intelligence-24gb-memory-512gb-ssd-space-black/"
    "JJGCQ8HVWL"
)
BESTBUY_API_BASE = "https://api.bestbuy.com/v1"
ZIP_CODES = [ "77001", "85001", "30301", "10001", "90210", "60601", "98101"]

PRICE_PATTERNS = [
    r'"customerPrice"\s*:\s*([\d\.]+)',
    r'"salePrice"\s*:\s*([\d.]+)',
    r'"currentPrice"\s*:\s*([\d.]+)',
    r'"customerPrice"\s*:\s*([\d.]+)',
    r'"priceToDisplay"\s*:\s*([\d.]+)',
    r'class="sr-only">\$([\d,]+\.\d{2})',
    r'"price"\s*:\s*([\d.]+)',
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sku() -> str:
    return os.environ.get("BESTBUY_SKU", DEFAULT_SKU)


def _product_url() -> str:
    return "https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-apple-m4-pro-chip-built-for-apple-intelligence-24gb-memory-512gb-ssd-space-black/JJGCQ8HVWL"


def _parse_price(text: str) -> float | None:
    cleaned = str(text).replace(",", "").strip()
    m = re.search(r"\$?([\d]+\.?\d*)", cleaned)
    if m:
        try:
            v = float(m.group(1))
            if 500 < v < 8000:
                return v
        except ValueError:
            pass
    return None


def _make_product(price: float, original_price: float | None = None, raw: dict | None = None) -> Product:
    return Product(
        source=Source.BESTBUY,
        name='MacBook Pro 14" M4 Pro 24GB 512GB Space Black',
        price=price,
        url=_product_url(),
        original_price=original_price,
        raw_data=raw,
    )


def _curl_session():
    """Crea una sesión curl_cffi que imita Chrome a nivel TLS."""
    try:
        from curl_cffi import requests as cf
        session = cf.Session(impersonate="chrome")
        session.headers.update({
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
        })
        return session
    except ImportError:
        logger.warning("curl_cffi no instalado. Corre: pip install curl-cffi")
        return None


# ── Capa 0: API oficial ────────────────────────────────────────────────────────

def _fetch_official_api(api_key: str, sku: str) -> Product | None:
    """
    API oficial de Best Buy.
    NOTA: Devuelve MSRP ($1,999) por acuerdo MAP de Apple,
    NO el precio con descuento temporal. Útil solo para disponibilidad.
    """
    url = f"{BESTBUY_API_BASE}/products/{sku}.json"
    params = {"apiKey": api_key, "show": "name,salePrice,regularPrice,onSale"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 404:
            logger.warning("API oficial: SKU %s no encontrado", sku)
            return None
        resp.raise_for_status()
        data = resp.json()
        sale = data.get("salePrice")
        if sale is None:
            return None
        logger.info("API oficial: $%.2f (puede ser MSRP, no precio promocional)", float(sale))
        return _make_product(
            float(sale),
            original_price=float(data["regularPrice"]) if data.get("regularPrice") else None,
            raw=data,
        )
    except Exception as e:
        logger.warning("API oficial error: %s", e)
        return None


# ── Capa 1: curl_cffi + página de producto (PRECIO REAL CON DESCUENTO) ────────

def _fetch_via_curl_cffi(sku: str) -> Product | None:
    """
    Scrape de la página de producto usando curl_cffi.

    curl_cffi imita el TLS fingerprint (JA3/JA4) de Chrome real,
    que es lo que Akamai valida primero. Esto bypasea la detección
    que bloqueaba requests, Camoufox y la VPN.

    Extrae el precio real incluyendo descuentos temporales de Apple
    que la API oficial NO devuelve por acuerdo MAP.
    """
    session = _curl_session()
    if session is None:
        return None

    url = _product_url()
    time.sleep(random.uniform(1.5, 3.5))

    try:
        # Paso 1: homepage para obtener cookies de sesión de Akamai
        session.get(
            "https://www.bestbuy.com/",
            headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                     "Upgrade-Insecure-Requests": "1"},
            timeout=20,
        )
        time.sleep(random.uniform(1.0, 2.0))

        # Paso 2: página del producto
        resp = session.get(
            url,
            headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                     "Referer": "https://www.bestbuy.com/",
                     "Upgrade-Insecure-Requests": "1"},
            timeout=30,
        )
        resp.raise_for_status()
        html = resp.text
        logger.debug("curl_cffi: página cargada, %d chars", len(html))

    except Exception as e:
        logger.debug("curl_cffi fetch failed: %s", e)
        return None

    # Buscar precio en el HTML
    for pattern in PRICE_PATTERNS:
        m = re.search(pattern, html)
        if m:
            price = _parse_price(m.group(1))
            if price:
                logger.info("curl_cffi página: $%.2f (patrón: %s)", price, pattern[:40])
                return _make_product(price)

    logger.debug("curl_cffi: precio no encontrado en HTML (%d chars)", len(html))
    return None

# def _fetch_via_scraperapi(sku: str) -> Product | None:
#     api_key = os.environ.get("SCRAPERAPI_KEY")
#     if not api_key:
#         logger.error("SCRAPERAPI_KEY no configurada en el archivo .env")
#         return None

#     target_url = _product_url()
    
#     # Vamos a usar la configuración exacta que usa el dashboard por defecto
#     payload = {
#         'api_key': api_key,
#         'url': target_url,
#         'country_code': 'us',
#         'device_type': 'desktop'
#         # Nota: Quitamos render=true y premium=true para igualar el test de la web
#     }
    
#     try:
#         logger.info("Iniciando petición vía ScraperAPI...")
#         resp = requests.get('https://api.scraperapi.com/', params=payload, timeout=60)
        
#         # Si ScraperAPI devuelve un error 500, imprimimos el mensaje exacto
#         if resp.status_code != 200:
#             logger.error(f"ScraperAPI falló con código {resp.status_code}: {resp.text}")
#             return None
            
#         html = resp.text
        
#         # Intentamos extraer el precio con tus patrones
#         for pattern in PRICE_PATTERNS:
#             m = re.search(pattern, html)
#             if m:
#                 price = _parse_price(m.group(1))
#                 if price:
#                     logger.info("ScraperAPI éxito: $%.2f (patrón: %s)", price, pattern[:40])
#                     return _make_product(price)
                    
#         # SI LLEGA AQUÍ: ScraperAPI funcionó (HTTP 200) pero el Regex falló.
#         # Guardamos el HTML para que lo puedas abrir y auditar.
#         debug_file = "scraperapi_debug.html"
#         with open(debug_file, "w", encoding="utf-8") as f:
#             f.write(html)
            
#         logger.warning(f"⚠️ ScraperAPI cargó la página, pero no encontró el precio. Revisa el archivo '{debug_file}' para ver el código fuente.")
#         return None

#     except Exception as e:
#         logger.error("Excepción en petición a ScraperAPI: %s", e)
        # return None

def _fetch_via_scraperapi(sku: str) -> Product | None:
    api_key = os.environ.get("SCRAPERAPI_KEY")
    if not api_key:
        logger.error("SCRAPERAPI_KEY no configurada en el archivo .env")
        return None

    #target_url = _product_url()
    target_url = "https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-apple-m4-pro-chip-built-for-apple-intelligence-24gb-memory-512gb-ssd-space-black/JJGCQ8HVWL"

    # LA FÓRMULA PARA BEST BUY: Premium SÍ (evita bloqueo), Render NO (evita timeout)
    payload = {
        'api_key': api_key,
        'url': target_url,
        'premium': 'true',      # Usamos 'premium' correctamente escrito
        'country_code': 'us',
        'device_type': 'desktop'
    }
    
    try:
        logger.info("Solicitando a ScraperAPI (Modo Premium residencial)...")
        # Timeout de 45s es suficiente porque no renderizamos JavaScript
        resp = requests.get('https://api.scraperapi.com/', params=payload, timeout=60)
        
        if resp.status_code != 200:
            logger.error(f"ScraperAPI falló con código {resp.status_code}: {resp.text}")
            return None
            
        html = resp.text
        
        # Guarda el HTML siempre para poder auditarlo si algo falla
        with open("scraperapi_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        # Agregamos el nuevo patrón "customerPrice" al inicio de la lista
        patterns = [
            r'"customerPrice"\s*:\s*([\d\.]+)',
            r'"salePrice"\s*:\s*([\d\.]+)',
            r'"price"\s*:\s*([\d\.]+)'
        ]
        
        for pattern in PRICE_PATTERNS:
            m = re.search(pattern, html)
            if m:
                price = _parse_price(m.group(1))
                if price:
                    logger.info(f"✅ Éxito! Precio encontrado: ${price:.2f} usando el patrón: {pattern}")
                    return _make_product(price)
                    
        logger.warning("ScraperAPI cargó exitosamente, pero no encontró el precio. Revisa 'scraperapi_debug.html'.")
        return None

    except Exception as e:
        logger.error(f"Excepción en la petición a ScraperAPI: {e}")
        return None

# ── Capa 2: curl_cffi + endpoints JSON internos ────────────────────────────────

def _fetch_via_curl_json(sku: str) -> Product | None:
    """
    Prueba endpoints JSON internos de Best Buy con sesión curl_cffi.
    Más rápido que scraping de HTML, pero menos confiable que la página.
    """
    session = _curl_session()
    if session is None:
        return None

    time.sleep(random.uniform(1.0, 2.0))

    # Endpoint 1: priceBlocks
    try:
        resp = session.get(
            f"https://www.bestbuy.com/api/3.0/priceBlocks?skuId={sku}",
            headers={"Accept": "application/json",
                     "Referer": _product_url()},
            timeout=15,
        )
        if resp.status_code == 200:
            raw = resp.text
            for pat in PRICE_PATTERNS:
                m = re.search(pat, raw)
                if m:
                    price = _parse_price(m.group(1))
                    if price:
                        logger.info("curl_cffi priceBlocks: $%.2f", price)
                        return _make_product(price)
    except Exception as e:
        logger.debug("curl_cffi priceBlocks: %s", e)

    # Endpoint 2: Falcor pdp/pricing
    try:
        zip_code = random.choice(ZIP_CODES)
        falcor_url = (
            f"https://www.bestbuy.com/api/tcfb/model.json"
            f'?paths=[["pdp","pricing","{sku}","salePrice"],'
            f'["pdp","pricing","{sku}","regularPrice"]]'
            f"&method=get"
        )
        resp = session.get(
            falcor_url,
            headers={"Accept": "application/json",
                     "Referer": _product_url()},
            timeout=15,
        )
        if resp.status_code == 200:
            raw = resp.text
            for pat in PRICE_PATTERNS:
                m = re.search(pat, raw)
                if m:
                    price = _parse_price(m.group(1))
                    if price:
                        logger.info("curl_cffi Falcor: $%.2f", price)
                        return _make_product(price)
    except Exception as e:
        logger.debug("curl_cffi Falcor: %s", e)

    return None


# ── Entry point público ────────────────────────────────────────────────────────

def fetch_bestbuy_product() -> Product | None:
    """
    Fetch precio de MacBook Pro de Best Buy.
    Orden de estrategias:
      0. API oficial      — si BESTBUY_API_KEY está configurada (devuelve MSRP)
      1. ScraperAPI       — Extrae el precio real con descuento delegando el bypass de Akamai
    """
    sku = _sku()
    
    # Capa 0: API oficial de Best Buy (si la tienes configurada)
    api_key = os.environ.get("BESTBUY_API_KEY", "").strip()
    if api_key:
        result = _fetch_official_api(api_key, sku)
        if result:
            return result

    # Capa 1: ScraperAPI (PRECIO REAL CON DESCUENTO)
    result = _fetch_via_scraperapi(sku)
    if result:
        return result

    logger.error("Best Buy: Todas las estrategias fallaron.")
    return None


# def fetch_bestbuy_product() -> Product | None:
#     """
#     Fetch precio de MacBook Pro 14" M4 Pro de Best Buy.

#     Orden de estrategias:
#       0. API oficial      — si BESTBUY_API_KEY está configurada
#                             (devuelve MSRP, no descuentos temporales)
#       1. curl_cffi + HTML — precio real con descuento (PRINCIPAL)
#       2. curl_cffi + JSON — endpoints internos como fallback rápido

#     curl_cffi bypasea Akamai Bot Manager imitando el TLS fingerprint
#     de Chrome, sin necesidad de VPN ni proxies.
#     """
#     sku = _sku()
#     api_key = os.environ.get("BESTBUY_API_KEY", "").strip()

#     # Capa 0: API oficial (solo para disponibilidad, precio puede ser MSRP)
#     if api_key:
#         result = _fetch_official_api(api_key, sku)
#         if result:
#             return result

#     # Capa 1: curl_cffi + página (precio real con descuento)
#     result = _fetch_via_curl_cffi(sku)
#     if result:
#         return result
#     logger.warning("curl_cffi página falló, intentando endpoints JSON...")

#     # Capa 2: curl_cffi + JSON interno
#     result = _fetch_via_curl_json(sku)
#     if result:
#         return result

#     logger.error("Best Buy: todas las estrategias fallaron")
#     return None