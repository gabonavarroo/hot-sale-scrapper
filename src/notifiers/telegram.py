"""Telegram push notification."""

import os

import requests

from src.models import Product

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_alert(product: Product, target_price: float) -> bool:
    """
    Send price alert via Telegram Bot API.

    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False

    text = (
        f"🔔 *Price Alert*\n\n"
        f"*{product.name[:80]}*\n\n"
        f"💰 ${product.price:,.2f} (target: ${target_price:,.2f})\n"
        f"📦 {product.source.value}\n\n"
        f"{product.url}"
    )

    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception:
        return False
