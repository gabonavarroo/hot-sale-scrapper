"""Entry point and scheduler for Hot Sale Scraper."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.comparator import get_target_price, record_and_check
from src.fetchers.apple import fetch_apple_refurbished
from src.fetchers.bestbuy import fetch_bestbuy_product
from src.notifiers.email import send_email_alert
from src.notifiers.telegram import send_telegram_alert
from src.storage import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_check() -> None:
    """Fetch prices, compare, and send alerts if needed."""
    target_price = get_target_price()
    if target_price <= 0:
        logger.warning("TARGET_PRICE_USD not set or 0 - alerts disabled")

    products: list = []

    # Best Buy
    try:
        bb = fetch_bestbuy_product()
        if bb:
            products.append(bb)
            logger.info("Best Buy: %s @ $%.2f", bb.name[:50], bb.price)
        else:
            logger.info("Best Buy: no product (API key missing or product unavailable)")
    except Exception as e:
        logger.exception("Best Buy fetch failed: %s", e)

    # Apple Refurbished
    try:
        apple_products = fetch_apple_refurbished()
        for p in apple_products:
            products.append(p)
            logger.info("Apple: %s @ $%.2f", p.name[:60], p.price)
        if not apple_products:
            logger.info("Apple Refurbished: no matching M4 Pro 12/16 512GB Space Black found")
    except Exception as e:
        logger.exception("Apple Refurbished fetch failed: %s", e)

    # Process each product
    for product in products:
        alert, is_new_low = record_and_check(product, target_price)
        if alert:
            logger.info("ALERT: %s at $%.2f (target $%.2f)", product.name[:50], product.price, target_price)
            if send_email_alert(product, target_price):
                logger.info("Email sent")
            else:
                logger.warning("Email not sent (check SMTP_USER/SMTP_PASS)")

            if send_telegram_alert(product, target_price):
                logger.info("Telegram sent")
            else:
                logger.debug("Telegram not sent (check TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")


def main() -> None:
    """Initialize DB and start scheduler."""
    init_db()
    logger.info("Hot Sale Scraper started")

    interval_minutes = int(os.environ.get("CHECK_INTERVAL_MINUTES", "30"))

    # Run once immediately, then every N minutes
    run_check()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="price_check",
    )

    logger.info("Scheduler: check every %d minutes", interval_minutes)
    scheduler.start()


if __name__ == "__main__":
    main()
