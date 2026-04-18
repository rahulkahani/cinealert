"""SMS alert delivery via email-to-SMS (Gmail SMTP)."""

import logging
import os
import smtplib
from email.mime.text import MIMEText

from providers.sms_gateways import get_gateway

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465


def compose_message(movie_name: str, theatre_display_name: str, ticket_url: str) -> str:
    """Compose the SMS alert message.

    Returns:
        Plain text message under 320 characters.
    """
    return (
        f"TICKETS LIVE: {movie_name}\n"
        f"IMAX 70mm @ {theatre_display_name}\n"
        f"Tickets are selling fast - book now before they sell out!\n"
        f"{ticket_url}"
    )


def send_sms(movie_name: str, theatre_display_name: str, ticket_url: str) -> bool:
    """Send an SMS alert to all configured phone numbers.

    Reads EMAIL, PASSWORD, and PHONE from environment variables.
    PHONE format: "5551234567:Rogers,5559876543:Bell"

    Returns:
        True if at least one message was sent successfully.
    """
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    phone_config = os.environ.get("PHONE")

    if not all([email, password, phone_config]):
        logger.error(
            "Missing environment variables. Need EMAIL, PASSWORD, and PHONE."
        )
        return False

    message_body = compose_message(movie_name, theatre_display_name, ticket_url)
    logger.info("Alert message (%d chars): %s", len(message_body), message_body)

    recipients = _parse_phone_config(phone_config)
    if not recipients:
        logger.error("No valid phone recipients parsed from PHONE env var.")
        return False

    any_sent = False
    for phone, carrier in recipients:
        try:
            gateway = get_gateway(carrier)
            to_addr = f"{phone}@{gateway}"
            success = _send_email(email, password, to_addr, message_body)
            if success:
                logger.info("SMS sent to %s via %s", phone, gateway)
                any_sent = True
        except ValueError as e:
            logger.error("Skipping %s: %s", phone, e)
        except Exception as e:
            logger.error("Failed to send SMS to %s: %s", phone, e)

    return any_sent


def _parse_phone_config(phone_config: str) -> list[tuple[str, str]]:
    """Parse PHONE env var into list of (phone_number, carrier) tuples."""
    recipients = []
    for entry in phone_config.split(","):
        entry = entry.strip()
        if ":" not in entry:
            logger.warning("Invalid phone entry (missing colon): '%s'", entry)
            continue
        phone, carrier = entry.split(":", 1)
        phone = phone.strip()
        carrier = carrier.strip()
        if phone and carrier:
            recipients.append((phone, carrier))
    return recipients


def _send_email(from_addr: str, password: str, to_addr: str, body: str) -> bool:
    """Send a plain text email via Gmail SMTP SSL."""
    msg = MIMEText(body)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = "CineAlert"

    try:
        with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
            server.login(from_addr, password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        return True
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to_addr, e)
        return False
