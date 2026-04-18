"""State management for duplicate alert prevention."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict:
    """Load the alert state from disk.

    Returns:
        A dict mapping "slug:alert_type" keys to alert records.
    """
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load state from %s: %s", path, e)
        return {}


def save_state(state: dict, path: Path = DEFAULT_STATE_PATH) -> None:
    """Write the alert state to disk."""
    try:
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.error("Failed to save state to %s: %s", path, e)


def was_alert_sent(state: dict, slug: str, alert_type: str) -> bool:
    """Check if an alert has already been sent for this movie + alert type."""
    key = f"{slug}:{alert_type}"
    return key in state


def record_alert(state: dict, slug: str, alert_type: str) -> None:
    """Record that an alert was sent."""
    key = f"{slug}:{alert_type}"
    state[key] = {
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "slug": slug,
        "alert_type": alert_type,
    }
