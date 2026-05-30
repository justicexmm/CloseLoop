"""
Quote Recovery Bot — main Flask application.
Exposes two webhooks:
  POST /webhook  — receives new quote data from Zapier / Housecall Pro
  POST /inbound  — receives inbound SMS replies forwarded by Telnyx
"""

import os
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify

import quote_database as db
from follow_up_scheduler import start_scheduler
from telnyx_sms import notify_contractor

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")

# ── App init ──────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Initialize database tables and start the background scheduler
db.init_db()
scheduler = start_scheduler()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_fields(data: dict, fields: list) -> list:
    """Return a list of any required field names that are missing or empty."""
    return [f for f in fields if not data.get(f)]


# ── Webhooks ──────────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def receive_quote():
    """
    Inbound webhook from Zapier / Housecall Pro.
    Expects JSON with: prospect_name, prospect_phone, contractor_phone,
    contractor_name, quote_amount, job_type, quote_id.
    Saves the quote and queues it for the 48-hour follow-up.
    """
    data = request.get_json(force=True, silent=True) or {}

    logger.info(f"[/webhook] Received payload: {data}")

    required = [
        "prospect_name", "prospect_phone", "contractor_phone",
        "contractor_name", "quote_amount", "job_type", "quote_id",
    ]
    missing = _require_fields(data, required)
    if missing:
        logger.warning(f"[/webhook] Missing fields: {missing}")
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    saved = db.save_quote(
        quote_id         = str(data["quote_id"]),
        prospect_name    = data["prospect_name"],
        prospect_phone   = data["prospect_phone"],
        contractor_name  = data["contractor_name"],
        contractor_phone = data["contractor_phone"],
        quote_amount     = str(data["quote_amount"]),
        job_type         = data["job_type"],
    )

    if not saved:
        # Duplicate — already in the system
        return jsonify({"status": "duplicate", "quote_id": data["quote_id"]}), 200

    logger.info(
        f"[/webhook] Quote {data['quote_id']} saved — "
        f"{data['prospect_name']} / {data['job_type']} / {data['quote_amount']}"
    )
    return jsonify({"status": "received", "quote_id": data["quote_id"]}), 200


@app.route("/inbound", methods=["POST"])
def receive_inbound_sms():
    """
    Inbound SMS webhook from Telnyx.
    Telnyx sends JSON; we pull from data.payload.from.phone_number and data.payload.text.
    Logs the reply and fires a notification to the contractor.
    """
    body = request.get_json(force=True, silent=True) or {}

    try:
        payload     = body["data"]["payload"]
        from_number = payload["from"]["phone_number"].strip()
        message_body = payload["text"].strip()
    except (KeyError, TypeError):
        logger.warning(f"[/inbound] Unexpected Telnyx payload shape: {body}")
        return ("", 204)

    if not from_number or not message_body:
        logger.warning("[/inbound] Empty from or text — ignoring.")
        return ("", 204)

    logger.info(f"[/inbound] SMS from {from_number}: {message_body!r}")

    # Look up the quote associated with this phone number
    quote = db.get_quote_by_phone(from_number)

    if not quote:
        logger.warning(f"[/inbound] No quote found for {from_number} — reply unmatched.")
        return ("", 200)

    quote_id         = quote["quote_id"]
    contractor_phone = quote["contractor_phone"]
    prospect_name    = quote["prospect_name"]

    # Persist the reply
    db.log_prospect_reply(quote_id, from_number, message_body)

    # Alert the contractor
    notify_contractor(contractor_phone, prospect_name)

    logger.info(
        f"[/inbound] Reply logged for quote {quote_id}; "
        f"contractor {contractor_phone} notified."
    )

    # Telnyx expects a plain 200 — no TwiML needed
    return ("", 200)


# ── Health check ──────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Simple liveness check."""
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()}), 200


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting Quote Recovery Bot on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
