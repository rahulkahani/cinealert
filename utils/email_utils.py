import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import List

import requests

from providers.sms_gateways import sms_gateways

_gateways_ci = {k.lower(): v for k, v in sms_gateways.items()}


def resolve_sms_addresses(phone_provider_pairs: List[str]) -> List[str]:
    addresses = []
    for pair in phone_provider_pairs:
        number, _, provider = pair.strip().partition(":")
        domain = _gateways_ci.get(provider.strip().lower())
        if not domain:
            logging.warning("Unknown SMS provider %r; skipping %r", provider, pair)
            continue
        addresses.append(f"{number.strip()}@{domain}")
    return addresses


def send_email(sender: str, password: str, recipients: List[str],
               subject: str, body: str) -> bool:
    if not recipients:
        return False
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, password)
            server.send_message(msg)
        logging.info("Email sent to %s", ", ".join(recipients))
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error(
            "Gmail authentication failed. Use an app password "
            "(https://support.google.com/accounts/answer/185833), not your "
            "regular account password."
        )
    except Exception as e:
        logging.error("Error sending email: %s", e)
    return False


def send_sms(sender: str, password: str, phone_provider_pairs: List[str],
             text: str) -> bool:
    addresses = resolve_sms_addresses(phone_provider_pairs or [])
    if not addresses:
        return False
    # Email-to-SMS gateways truncate around 160 chars; keep it terse and
    # subject-less so the body isn't pushed out of the message.
    return send_email(sender, password, addresses, "", text[:300])


def send_ntfy(topic: str, title: str, body: str, click_url: str = "") -> bool:
    """Push notification via ntfy.sh — instant, free, works on iOS/Android."""
    if not topic:
        return False
    headers = {
        "Title": title.encode("ascii", "ignore").decode(),
        "Priority": "urgent",
        "Tags": "rotating_light,movie_camera",
    }
    if click_url:
        headers["Click"] = click_url
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        logging.info("ntfy push sent to topic %s", topic)
        return True
    except requests.RequestException as e:
        logging.error("Error sending ntfy push: %s", e)
        return False
