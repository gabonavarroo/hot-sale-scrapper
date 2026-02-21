"""Telegram push notification."""

import logging
import os

import requests

from src.models import Product

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_alert(product: Product, target_price: float) -> bool:
    """
    Send price alert via Telegram Bot API.

    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("Telegram: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    text = (
        f"🔔 <b>Price Alert</b>\n\n"
        f"<b>{product.name[:80]}</b>\n\n"
        f"💰 ${product.price:,.2f} (target: ${target_price:,.2f})\n"
        f"📦 {product.source.value}\n\n"
        f"{product.url}"
    )

    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        logger.debug("Telegram: sending alert for %s", product.name[:50])
        logger.debug("Telegram payload: %s", payload)
        resp = requests.post(url, json=payload, timeout=10)
        logger.debug("Telegram response status: %d", resp.status_code)
        
        if resp.status_code != 200:
            try:
                error_data = resp.json()
                logger.error("Telegram API error (status %d): %s", resp.status_code, error_data)
            except:
                logger.error("Telegram error (status %d): %s", resp.status_code, resp.text)
        
        resp.raise_for_status()
        logger.info("Telegram: alert sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Telegram request failed: %s", e)
        return False
    except Exception as e:
        logger.error("Telegram unexpected error: %s", e, exc_info=True)
        return False
