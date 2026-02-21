"""Email notification via SMTP (Gmail)."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.models import Product

logger = logging.getLogger(__name__)


def send_email_alert(product: Product, target_price: float) -> bool:
    """
    Send price alert email.

    Uses SMTP_USER and SMTP_PASS (Gmail App Password).
    SMTP_TO defaults to SMTP_USER if not set.
    """
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to_addr = os.environ.get("SMTP_TO", user)

    if not user or not password:
        logger.warning("Email: SMTP_USER or SMTP_PASS not set")
        return False

    subject = f"Price Alert: {product.name[:50]}... at ${product.price:,.2f}"
    body = f"""
Hot Sale Scraper - Price Alert

Product: {product.name}
Current Price: ${product.price:,.2f}
Target Price: ${target_price:,.2f}
Source: {product.source.value}

URL: {product.url}

Get it before it's gone!
"""

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body.strip(), "plain"))

    try:
        logger.debug("Email: sending alert to %s", to_addr)
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, to_addr, msg.as_string())
        logger.info("Email: alert sent successfully")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error("Email authentication failed: %s", e)
        return False
    except smtplib.SMTPException as e:
        logger.error("Email SMTP error: %s", e)
        return False
    except Exception as e:
        logger.error("Email unexpected error: %s", e, exc_info=True)
        return False
