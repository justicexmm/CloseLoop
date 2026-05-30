"""
Telnyx SMS handler for the Quote Recovery Bot.
Sends follow-up messages to prospects and alert notifications to contractors.
"""

import os
import logging
import telnyx

logger = logging.getLogger(__name__)

telnyx.api_key = os.getenv("TELNYX_API_KEY")

TELNYX_FROM_NUMBER       = os.getenv("TELNYX_FROM_NUMBER", "+16183666858")
TELNYX_MESSAGING_PROFILE = os.getenv("TELNYX_MESSAGING_PROFILE_ID", "40019e76-5746-4a70-8cdb-fccfe5f0e4d7")


def send_sms(to_number: str, message_body: str) -> str | None:
    """
    Send an SMS via Telnyx V2. Returns the message ID on success, None on failure.
    Phone numbers must be in E.164 format (e.g. +15551234567).
    """
    try:
        msg = telnyx.messages.create(
            from_=TELNYX_FROM_NUMBER,
            to=to_number,
            text=message_body,
            messaging_profile_id=TELNYX_MESSAGING_PROFILE,
        )
        logger.info(f"[Telnyx] SMS sent to {to_number} — ID: {msg.id}")
        return msg.id
    except Exception as e:
        logger.error(f"[Telnyx] Failed to send SMS to {to_number}: {e}")
        return None


def send_follow_up(prospect_phone: str, message_body: str) -> str | None:
    """Send the AI-generated follow-up message to the prospect."""
    logger.info(f"[Telnyx] Sending follow-up to prospect {prospect_phone}.")
    return send_sms(prospect_phone, message_body)


def notify_contractor(contractor_phone: str, prospect_name: str) -> str | None:
    """
    Fire an alert SMS to the contractor when their prospect replies.
    Keeps the message short and actionable.
    """
    body = (
        f"Your quote for {prospect_name} just got a reply. "
        f"Log in to close it!"
    )
    logger.info(f"[Telnyx] Notifying contractor {contractor_phone} about {prospect_name}.")
    return send_sms(contractor_phone, body)
