"""SQLite persistence for price history."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src.models import PriceRecord, Source


def get_db_path() -> Path:
    """Get database path from env or default."""
    path = os.environ.get("DB_PATH", "data/prices.db")
    return Path(path)


@contextmanager
def get_connection():
    """Context manager for SQLite connection."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                product_name TEXT NOT NULL,
                price REAL NOT NULL,
                url TEXT,
                original_price REAL,
                recorded_at TIMESTAMP NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_recorded
            ON price_history(source, recorded_at)
        """)


def save_price(record: PriceRecord) -> None:
    """Save a price record to the database."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO price_history (source, product_name, price, url, original_price, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.source,
                record.product_name,
                record.price,
                record.url,
                record.original_price,
                record.recorded_at.isoformat(),
            ),
        )


def get_last_price(source: Source, product_name: str) -> float | None:
    """Get the most recent price for a product from a source."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT price FROM price_history
            WHERE source = ? AND product_name = ?
            ORDER BY recorded_at DESC LIMIT 1
            """,
            (source.value, product_name),
        ).fetchone()
    return row["price"] if row else None
