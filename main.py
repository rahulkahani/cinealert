"""CineAlert — monitors Cineplex for IMAX 70mm ticket availability."""

import json
import logging
import sys
from pathlib import Path

from utils.scraper import fetch_movie_data, check_imax_70mm_showtimes, text_search_70mm
from utils.alert import send_sms
from utils.state import load_state, save_state, was_alert_sent, record_alert

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
LOG_DIR = Path(__file__).resolve().parent / "logs"

# Alert types
ALERT_FORMAT_DETECTED = "format_detected"
ALERT_SHOWTIMES_LIVE = "showtimes_live"


def setup_logging() -> None:
    """Configure logging to file and stdout."""
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "main.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    """Load config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def check_movie(movie: dict, config: dict, state: dict) -> None:
    """Check a single movie for IMAX 70mm availability and send alerts."""
    logger = logging.getLogger(__name__)
    slug = movie["slug"]
    name = movie["name"]
    ticket_url = movie["ticket_url"]
    theatre = config["theatre"]
    theatre_display = config["theatre_display_name"]
    target_formats = {f.upper() for f in config["target_formats"]}

    logger.info("Checking: %s (%s)", name, slug)

    data = fetch_movie_data(slug)
    if data is None:
        logger.warning("Could not fetch data for %s, skipping.", slug)
        return

    formats = data.get("formats", [])
    has_showtimes = data.get("has_showtimes", False)
    page_props = data.get("raw_page_props", {})

    logger.info(
        "%s — formats: %s, hasShowtimes: %s",
        name, formats, has_showtimes,
    )

    # Stage 1: Format Watch — detect new format IDs appearing
    # (Format IDs are integers; we can't directly map them to IMAX/70MM
    #  without a known mapping, so we flag any change in formats array)
    if formats and not was_alert_sent(state, slug, ALERT_FORMAT_DETECTED):
        logger.info("New formats detected for %s: %s", name, formats)
        sent = send_sms(
            movie_name=name,
            theatre_display_name=theatre_display,
            ticket_url=ticket_url,
        )
        if sent:
            record_alert(state, slug, ALERT_FORMAT_DETECTED)
            logger.info("Format detection alert sent for %s", name)

    # Stage 2: Showtime Watch — check for actual IMAX 70mm showtimes at target theatre
    if has_showtimes and not was_alert_sent(state, slug, ALERT_SHOWTIMES_LIVE):
        imax_70mm_found = check_imax_70mm_showtimes(page_props, theatre)

        if imax_70mm_found:
            logger.info("IMAX 70mm showtimes LIVE for %s at %s!", name, theatre)
            sent = send_sms(
                movie_name=name,
                theatre_display_name=theatre_display,
                ticket_url=ticket_url,
            )
            if sent:
                record_alert(state, slug, ALERT_SHOWTIMES_LIVE)
                logger.info("Showtime alert sent for %s", name)


def main() -> None:
    """Main entry point — check all configured movies."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("CineAlert starting check cycle")

    config = load_config()
    state = load_state()

    for movie in config["movies"]:
        try:
            check_movie(movie, config, state)
        except Exception:
            logger.exception("Unexpected error checking %s", movie.get("slug", "?"))

    save_state(state)
    logger.info("Check cycle complete.")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
