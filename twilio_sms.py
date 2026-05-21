"""
Twilio SMS handler for the Quote Recovery Bot.
Sends follow-up messages to prospects and alert notifications to contractors.
"""

import os
import logging
from twilio.rest import Client

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

_client = None


def _get_client():
    """Lazy-initialize the Twilio client."""
    global _client
    if _client is None:
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _client


def send_sms(to_number, message_body):
    """
    Send an SMS via Twilio. Returns the message SID on success, None on failure.
    Phone numbers must be in E.164 format (e.g. +15551234567).
    """
    try:
        client = _get_client()
        msg = client.messages.create(
            body=message_body,
            from_=TWILIO_FROM_NUMBER,
            to=to_number
        )
        logger.info(f"[Twilio] SMS sent to {to_number} — SID: {msg.sid}")
        return msg.sid
    except Exception as e:
        logger.error(f"[Twilio] Failed to send SMS to {to_number}: {e}")
        return None


def send_follow_up(prospect_phone, message_body):
    """Send the AI-generated follow-up message to the prospect."""
    logger.info(f"[Twilio] Sending follow-up to prospect {prospect_phone}.")
    return send_sms(prospect_phone, message_body)


def notify_contractor(contractor_phone, prospect_name):
    """
    Fire an alert SMS to the contractor when their prospect replies.
    Keeps the message short and actionable.
    """
    body = (
        f"Your quote for {prospect_name} just got a reply. "
        f"Log in to close it!"
    )
    logger.info(f"[Twilio] Notifying contractor {contractor_phone} about {prospect_name}.")
    return send_sms(contractor_phone, body)
