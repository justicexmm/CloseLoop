"""
Gemini API message generator for the Quote Recovery Bot.
Produces personalized follow-up SMS messages under 160 characters.
"""

import os
import logging
from google import genai

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

_client = None


def _get_client():
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate_follow_up_message(prospect_name, job_type, quote_amount, contractor_name):
    """
    Ask Gemini to write a friendly, non-pushy follow-up SMS.

    Returns the message string, or a safe fallback if the API call fails.
    The message must be under 160 characters to fit in a single SMS.
    """
    prompt = f"""Write a follow-up SMS for a home service quote. Keep it under 160 characters total.

Details:
- Prospect first name: {prospect_name.split()[0]}
- Job type: {job_type}
- Quote amount: {quote_amount}
- Contractor/company name: {contractor_name}

Rules:
- Friendly, casual tone — like a text from a real person
- Do NOT be pushy or salesy
- Create soft urgency (availability, schedule this week, etc.)
- Do NOT include a URL or signature
- Return ONLY the SMS text, nothing else

Example style: "Hey Sarah, just checking in on that HVAC quote from Mike's Heating — still happy to get you scheduled this week!"
"""

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        message = response.text.strip().strip('"')

        # Enforce 160-char limit — truncate at last word boundary if needed
        if len(message) > 160:
            message = message[:157].rsplit(" ", 1)[0] + "..."

        logger.info(f"[Gemini] Generated message ({len(message)} chars): {message}")
        return message

    except Exception as e:
        logger.error(f"[Gemini] API call failed: {e}")
        # Safe fallback that still sounds human
        first_name = prospect_name.split()[0]
        return (
            f"Hey {first_name}, just checking in on your {job_type} quote from "
            f"{contractor_name} — happy to get you scheduled this week!"
        )[:160]


def generate_second_follow_up_message(prospect_name, job_type, quote_amount, contractor_name):
    """
    Ask Gemini to write a second follow-up SMS with closing energy.
    Lighter on scarcity than the first message — warm, low-pressure, final nudge.

    Returns the message string, or a safe fallback if the API call fails.
    The message must be under 160 characters to fit in a single SMS.
    """
    prompt = f"""Write a second and final follow-up SMS for a home service quote. Keep it under 160 characters total.

Details:
- Prospect first name: {prospect_name.split()[0]}
- Job type: {job_type}
- Quote amount: {quote_amount}
- Contractor/company name: {contractor_name}

Rules:
- Warmer and lighter tone than the first follow-up — this is the last message
- Closing energy: make it easy for them to say yes or no, no pressure
- A soft "just wanted to leave the door open" vibe
- Do NOT be pushy or salesy
- Do NOT include a URL or signature
- Return ONLY the SMS text, nothing else

Example style: "Hey Sarah, no worries if the timing isn't right — just wanted to leave the door open on that HVAC quote. Happy to help whenever you're ready!"
"""

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        message = response.text.strip().strip('"')

        # Enforce 160-char limit — truncate at last word boundary if needed
        if len(message) > 160:
            message = message[:157].rsplit(" ", 1)[0] + "..."

        logger.info(f"[Gemini] Generated second follow-up ({len(message)} chars): {message}")
        return message

    except Exception as e:
        logger.error(f"[Gemini] API call failed for second follow-up: {e}")
        first_name = prospect_name.split()[0]
        return (
            f"Hey {first_name}, no pressure at all — just wanted to leave the door open "
            f"on that {job_type} quote from {contractor_name}. Here whenever you're ready!"
        )[:160]
