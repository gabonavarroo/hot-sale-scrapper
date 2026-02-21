"""Entry point and scheduler for Hot Sale Scraper."""

import logging
import os
import random
import sys
import time
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
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_check() -> None:
    """Fetch prices, compare, and send alerts if needed."""
    target_price = get_target_price()
    if target_price <= 0:
        logger.warning("TARGET_PRICE_USD not set or 0 — alerts disabled")

    products: list = []

    # ── Best Buy ───────────────────────────────────────────────────────────────
    try:
        bb = fetch_bestbuy_product()
        if bb:
            products.append(bb)
            logger.info("Best Buy: %s @ $%.2f", bb.name[:50], bb.price)
        else:
            logger.info("Best Buy: no price retrieved (all strategies failed)")
    except Exception as e:
        logger.exception("Best Buy fetch error: %s", e)

    # ── Apple Refurbished ─────────────────────────────────────────────────────
    try:
        apple_products = fetch_apple_refurbished()
        for p in apple_products:
            products.append(p)
            logger.info("Apple: %s @ $%.2f", p.name[:60], p.price)
        if not apple_products:
            logger.info("Apple Refurbished: target model not currently listed")
    except Exception as e:
        logger.exception("Apple Refurbished fetch error: %s", e)

    # ── Compare & notify ──────────────────────────────────────────────────────
    for product in products:
        alert, is_new_low = record_and_check(product, target_price)
        if alert:
            logger.info(
                "🚨 ALERT: %s at $%.2f (target $%.2f)",
                product.name[:50], product.price, target_price,
            )
            if send_email_alert(product, target_price):
                logger.info("✉️  Email sent")
            else:
                logger.warning("Email not sent — check SMTP_USER / SMTP_PASS")

            if send_telegram_alert(product, target_price):
                logger.info("📱 Telegram sent")
            else:
                logger.warning("Telegram not sent — check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        elif is_new_low and target_price > 0:
            logger.info(
                "New price low: $%.2f (still above target $%.2f)",
                product.price, target_price,
            )


def run_check_with_jitter() -> None:
    """
    Add randomized jitter before each scheduled check.

    Jitter avoids the perfectly-regular request pattern that bot-detection
    systems flag as automation.  The base interval is defined by
    CHECK_INTERVAL_MINUTES; each run is preceded by a random delay of
    0–JITTER_MAX_SECONDS seconds (default 0–180 s = 0–3 min).
    """
    jitter_max = int(os.environ.get("JITTER_MAX_SECONDS", "180"))
    delay = random.uniform(0, jitter_max)
    logger.debug("Jitter: sleeping %.1f s before check", delay)
    time.sleep(delay)
    run_check()


def main() -> None:
    """Initialize DB, run once immediately, then start the scheduler."""
    init_db()
    logger.info("🚀 Hot Sale Scraper started")
    logger.info("Target price: $%s", os.environ.get("TARGET_PRICE_USD", "not set"))

    interval_minutes = int(os.environ.get("CHECK_INTERVAL_MINUTES", "30"))
    jitter_max = int(os.environ.get("JITTER_MAX_SECONDS", "180"))

    logger.info(
        "Scheduler: every ~%d min ± %d s jitter",
        interval_minutes, jitter_max,
    )

    # Run once immediately on startup (no jitter on first run so you see output fast)
    run_check()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_check_with_jitter,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="price_check",
        max_instances=1,          # Prevent overlapping runs
        misfire_grace_time=300,   # 5 min grace if a run is missed
    )
    scheduler.start()


if __name__ == "__main__":
    main()