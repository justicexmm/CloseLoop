"""
APScheduler-based follow-up engine for the Quote Recovery Bot.
Checks every hour for pending quotes older than 48 hours and sends follow-ups.
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import quote_database as db
from claude_message_generator import generate_follow_up_message, generate_second_follow_up_message
from telnyx_sms import send_follow_up

logger = logging.getLogger(__name__)

FOLLOW_UP_HOURS       = int(os.getenv("FOLLOW_UP_HOURS", "48"))
SECOND_FOLLOW_UP_DAYS = int(os.getenv("SECOND_FOLLOW_UP_DAYS", "7"))


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


def check_and_send_second_follow_ups():
    """
    Second follow-up job — runs on the same interval as the first.
    Finds quotes with status=followed_up whose follow_up_sent_at is older
    than SECOND_FOLLOW_UP_DAYS (default 7). Sends a lighter closing message
    and marks them followed_up_2. Quotes already at followed_up_2 are never touched.
    """
    logger.info("[Scheduler] Running second follow-up check...")

    followed_up = db.get_followed_up_quotes()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=SECOND_FOLLOW_UP_DAYS)

    sent_count = 0

    for quote in followed_up:
        try:
            follow_up_sent_at = quote.get("follow_up_sent_at")
            if not follow_up_sent_at:
                logger.debug(f"[Scheduler] Quote {quote['quote_id']} has no follow_up_sent_at — skipping.")
                continue

            first_sent = datetime.fromisoformat(follow_up_sent_at)
            if first_sent.tzinfo is None:
                first_sent = first_sent.replace(tzinfo=timezone.utc)

            if first_sent > cutoff:
                secs_remaining = int((first_sent + timedelta(days=SECOND_FOLLOW_UP_DAYS) - now).total_seconds())
                logger.debug(
                    f"[Scheduler] Quote {quote['quote_id']} not ready for second follow-up "
                    f"(~{secs_remaining}s remaining)."
                )
                continue

            quote_id        = quote["quote_id"]
            prospect_name   = quote["prospect_name"]
            prospect_phone  = quote["prospect_phone"]
            job_type        = quote["job_type"]
            quote_amount    = quote["quote_amount"]
            contractor_name = quote["contractor_name"]

            logger.info(
                f"[Scheduler] Sending second follow-up for quote {quote_id} "
                f"({prospect_name}, {job_type})."
            )

            # Mark followed_up_2 BEFORE sending to prevent duplicate sends on failure
            db.update_quote_status(quote_id, "followed_up_2")

            message = generate_second_follow_up_message(
                prospect_name=prospect_name,
                job_type=job_type,
                quote_amount=quote_amount,
                contractor_name=contractor_name,
            )

            sid = send_follow_up(prospect_phone, message)

            if sid:
                logger.info(f"[Scheduler] Second follow-up delivered for {quote_id} (SID: {sid}).")
                sent_count += 1
            else:
                logger.warning(f"[Scheduler] Second follow-up SMS failed for {quote_id} — status kept as followed_up_2.")

        except Exception as e:
            logger.error(f"[Scheduler] Error processing second follow-up for {quote.get('quote_id')}: {e}")

    logger.info(f"[Scheduler] Second follow-up check complete. {sent_count} message(s) sent.")


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
    scheduler.add_job(
        check_and_send_second_follow_ups,
        trigger="interval",
        minutes=2,  # TEST MODE — change back to hours=1
        id="second_follow_up_check",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    scheduler.start()
    logger.info("[Scheduler] Background scheduler started (interval: 2 minutes — TEST MODE).")
    return scheduler
