"""Cineplex page scraper — extracts __NEXT_DATA__ from movie pages."""

from __future__ import annotations

import json
import logging
import random
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30


def fetch_movie_data(slug: str) -> dict | None:
    """Fetch a Cineplex movie page and extract structured data from __NEXT_DATA__.

    Args:
        slug: The movie's URL slug (e.g., "the-odyssey").

    Returns:
        A dict with movie details, or None if extraction fails.
    """
    url = f"https://www.cineplex.com/movie/{slug}"

    # Random delay to avoid exact polling intervals
    delay = random.uniform(0, 60)
    logger.info("Waiting %.1f seconds before fetching %s", delay, slug)
    time.sleep(delay)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None

    return _parse_next_data(response.text, slug)


def _parse_next_data(html: str, slug: str) -> dict | None:
    """Parse __NEXT_DATA__ JSON from a Cineplex movie page.

    Returns a dict with keys: name, slug, release_date, formats,
    has_showtimes, poster_url, raw_page_props.
    """
    soup = BeautifulSoup(html, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__")

    if not script_tag or not script_tag.string:
        logger.error("No __NEXT_DATA__ script tag found for slug '%s'", slug)
        return None

    try:
        next_data = json.loads(script_tag.string)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse __NEXT_DATA__ JSON for '%s': %s", slug, e)
        return None

    try:
        page_props = next_data["props"]["pageProps"]
        movie = page_props["movieDetails"]
    except KeyError:
        logger.error(
            "Unexpected __NEXT_DATA__ structure for '%s' — "
            "missing props.pageProps.movieDetails",
            slug,
        )
        return None

    return {
        "name": movie.get("name", slug),
        "slug": movie.get("slug", slug),
        "release_date": movie.get("releaseDate"),
        "formats": movie.get("formats", []),
        "has_showtimes": movie.get("hasShowtimes", False),
        "poster_url": movie.get("mediumPosterImageUrl"),
        "raw_page_props": page_props,
    }


def check_imax_70mm_showtimes(
    page_props: dict, theatre_slug: str
) -> bool:
    """Check if any showtimes at the target theatre have both IMAX and 70MM tags.

    Searches through the page props for showtime data containing
    experience/format attributes matching IMAX + 70MM at the given theatre.

    Args:
        page_props: The raw pageProps dict from __NEXT_DATA__.
        theatre_slug: The theatre's URL slug (e.g., "cineplex-cinemas-vaughan").

    Returns:
        True if IMAX 70mm showtimes exist at the theatre.
    """
    # The showtime data structure can vary; search broadly
    showtimes = _extract_showtimes(page_props)

    for showtime in showtimes:
        theatre = showtime.get("theatreSlug", "") or showtime.get("slug", "")
        if theatre_slug not in theatre.lower():
            continue

        experiences = showtime.get("experiences", [])
        attrs = set()
        for exp in experiences:
            attr = exp.get("vistaAttribute", "") or exp.get("experienceType", "")
            if attr:
                attrs.add(attr.upper())

        if "IMAX" in attrs and "70MM" in attrs:
            logger.info(
                "Found IMAX 70mm showtime at %s: %s", theatre_slug, showtime
            )
            return True

    return False


def _extract_showtimes(page_props: dict) -> list:
    """Recursively search page props for showtime-like data."""
    showtimes = []

    if isinstance(page_props, dict):
        # Check common keys where showtimes might live
        for key in ("showtimes", "dates", "sessions", "performances"):
            if key in page_props and isinstance(page_props[key], list):
                showtimes.extend(page_props[key])

        for value in page_props.values():
            if isinstance(value, (dict, list)):
                showtimes.extend(_extract_showtimes(value))

    elif isinstance(page_props, list):
        for item in page_props:
            if isinstance(item, (dict, list)):
                showtimes.extend(_extract_showtimes(item))

    return showtimes


def text_search_70mm(html: str) -> bool:
    """Backup detection: search raw page text for 70mm references."""
    lower = html.lower()
    return "70mm" in lower or "70 mm" in lower
