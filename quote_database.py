"""
SQLite database handler for the Quote Recovery Bot.
Manages quotes and prospect replies with full lifecycle tracking.
"""

import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "quotes.db")


def get_connection():
    """Open and return a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS quotes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id            TEXT    UNIQUE NOT NULL,
                prospect_name       TEXT    NOT NULL,
                prospect_phone      TEXT    NOT NULL,
                contractor_name     TEXT    NOT NULL,
                contractor_phone    TEXT    NOT NULL,
                quote_amount        TEXT    NOT NULL,
                job_type            TEXT    NOT NULL,
                sent_at             TEXT    NOT NULL,
                follow_up_sent_at   TEXT,
                status              TEXT    NOT NULL DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS replies (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id        TEXT    NOT NULL,
                prospect_phone  TEXT    NOT NULL,
                message_body    TEXT    NOT NULL,
                received_at     TEXT    NOT NULL
            );
        """)
        conn.commit()
        logger.info("[DB] Tables initialized.")
    finally:
        conn.close()


def save_quote(quote_id, prospect_name, prospect_phone, contractor_name,
               contractor_phone, quote_amount, job_type):
    """
    Insert a new quote record with status=pending.
    Returns True on success, False if quote_id already exists.
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO quotes
                (quote_id, prospect_name, prospect_phone, contractor_name,
                 contractor_phone, quote_amount, job_type, sent_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            quote_id, prospect_name, prospect_phone, contractor_name,
            contractor_phone, quote_amount, job_type,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        logger.info(f"[DB] Saved quote {quote_id} for {prospect_name}.")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"[DB] Quote {quote_id} already exists — skipping.")
        return False
    finally:
        conn.close()


def get_pending_quotes():
    """
    Return all quotes with status=pending.
    The scheduler uses this to find quotes ready for follow-up.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM quotes WHERE status = 'pending'"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_followed_up_quotes():
    """
    Return all quotes with status=followed_up.
    The scheduler filters these by follow_up_sent_at age to find ones
    ready for the second follow-up.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM quotes WHERE status = 'followed_up'"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_quote_status(quote_id, new_status):
    """
    Update the status field for a given quote.
    Valid statuses: pending, followed_up, followed_up_2, closed, cancelled.
    Also stamps follow_up_sent_at when transitioning to followed_up.
    """
    conn = get_connection()
    try:
        if new_status == "followed_up":
            conn.execute("""
                UPDATE quotes
                SET status = ?, follow_up_sent_at = ?
                WHERE quote_id = ?
            """, (new_status, datetime.utcnow().isoformat(), quote_id))
        else:
            conn.execute(
                "UPDATE quotes SET status = ? WHERE quote_id = ?",
                (new_status, quote_id)
            )
        conn.commit()
        logger.info(f"[DB] Quote {quote_id} → status={new_status}.")
    finally:
        conn.close()


def log_prospect_reply(quote_id, prospect_phone, message_body):
    """Insert a record of an inbound SMS reply from a prospect."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO replies (quote_id, prospect_phone, message_body, received_at)
            VALUES (?, ?, ?, ?)
        """, (quote_id, prospect_phone, message_body, datetime.utcnow().isoformat()))
        conn.commit()
        logger.info(f"[DB] Logged reply from {prospect_phone} on quote {quote_id}.")
    finally:
        conn.close()


def get_quote_by_phone(prospect_phone):
    """
    Look up the most recent quote associated with a phone number.
    Used when routing an inbound SMS to the right quote record.
    """
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM quotes
            WHERE prospect_phone = ?
            ORDER BY sent_at DESC
            LIMIT 1
        """, (prospect_phone,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
