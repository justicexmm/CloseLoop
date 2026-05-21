"""
APScheduler-based follow-up engine for the Quote Recovery Bot.
Checks every hour for pending quotes older than 48 hours and sends follow-ups.
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import quote_database as db
from claude_message_generator import generate_follow_up_message
from twilio_sms import send_follow_up

logger = logging.getLogger(__name__)

FOLLOW_UP_HOURS = int(os.getenv("FOLLOW_UP_HOURS", "48"))


def check_and_send_follow_ups():
    """
    Main scheduler job — runs every hour.
    Finds pending quotes past the follow-up window and sends one message per quote.
    Marks each as followed_up immediately to prevent duplicate sends.
    """
    logger.info("[Scheduler] Running follow-up check...")

    pending = db.get_pending_quotes()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=2)  # TEST MODE — change back to timedelta(hours=FOLLOW_UP_HOURS)

    sent_count = 0

    for quote in pending:
        try:
            sent_at = datetime.fromisoformat(quote["sent_at"])

            # Ensure timezone-aware comparison
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)

            if sent_at > cutoff:
                # Not old enough yet
                secs_remaining = (sent_at + timedelta(minutes=2) - now).seconds  # TEST MODE
                logger.debug(
                    f"[Scheduler] Quote {quote['quote_id']} not ready "
                    f"(~{secs_remaining}s remaining)."
                )
                continue

            quote_id      = quote["quote_id"]
            prospect_name = quote["prospect_name"]
            prospect_phone = quote["prospect_phone"]
            job_type      = quote["job_type"]
            quote_amount  = quote["quote_amount"]
            contractor_name = quote["contractor_name"]

            logger.info(
                f"[Scheduler] Sending follow-up for quote {quote_id} "
                f"({prospect_name}, {job_type})."
            )

            # Mark followed_up BEFORE sending so a crash mid-send doesn't cause duplicates
            db.update_quote_status(quote_id, "followed_up")

            message = generate_follow_up_message(
                prospect_name=prospect_name,
                job_type=job_type,
                quote_amount=quote_amount,
                contractor_name=contractor_name,
            )

            sid = send_follow_up(prospect_phone, message)

            if sid:
                logger.info(f"[Scheduler] Follow-up delivered for {quote_id} (SID: {sid}).")
                sent_count += 1
            else:
                logger.warning(f"[Scheduler] Follow-up SMS failed for {quote_id} — status kept as followed_up.")

        except Exception as e:
            logger.error(f"[Scheduler] Error processing quote {quote.get('quote_id')}: {e}")

    logger.info(f"[Scheduler] Check complete. {sent_count} follow-up(s) sent.")


def start_scheduler():
    """
    Start the background scheduler.
    Runs check_and_send_follow_ups immediately on start, then every hour.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_and_send_follow_ups,
        trigger="interval",
        minutes=2,  # TEST MODE — change back to hours=1
        id="follow_up_check",
        replace_existing=True,
        next_run_time=datetime.now(),  # fire immediately on startup
    )
    scheduler.start()
    logger.info("[Scheduler] Background scheduler started (interval: 2 minutes — TEST MODE).")
    return scheduler
