"""Canadian carrier SMS gateway domains for email-to-SMS."""

GATEWAYS = {
    "rogers": "pcs.rogers.com",
    "bell": "txt.bell.ca",
    "telus": "msg.telus.com",
    "fido": "fido.ca",
    "koodo": "msg.koodomobile.com",
    "virgin": "vmobile.ca",
    "chatr": "pcs.rogers.com",
    "freedom": "txt.freedommobile.ca",
    "sasktel": "sms.sasktel.com",
    "videotron": "sms.videotron.ca",
    "public_mobile": "msg.telus.com",
    "lucky_mobile": "txt.bell.ca",
}


def get_gateway(carrier: str) -> str:
    """Return the SMS gateway domain for a given carrier name.

    Args:
        carrier: Carrier name (case-insensitive, underscores or spaces).

    Returns:
        Gateway domain string.

    Raises:
        ValueError: If carrier is not recognized.
    """
    key = carrier.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in GATEWAYS:
        raise ValueError(
            f"Unknown carrier '{carrier}'. "
            f"Supported: {', '.join(sorted(GATEWAYS.keys()))}"
        )
    return GATEWAYS[key]
