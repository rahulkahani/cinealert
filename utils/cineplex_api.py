"""Client for the Cineplex showtimes API (apis.cineplex.com).

The Cineplex website is a Next.js app that fetches showtimes from
https://apis.cineplex.com/prod/cpx/theatrical/api/v1/showtimes with an
`Ocp-Apim-Subscription-Key` header (a public key embedded in the site's own
JavaScript). Both the key and the theatre's numeric locationId can rotate or
be unknown, so this client can *discover* them at runtime by loading the
theatre page in headless Chrome and capturing the network request the page
itself makes. The discovered URL template and headers are cached in the
state file and replayed with plain `requests` afterwards.

Session extraction is deliberately schema-tolerant: instead of hard-coding
the exact JSON shape, it walks the payload looking for dicts that carry a
show start time, and picks up film names / experience labels (IMAX, 70MM
FILM, ...) from the surrounding context. That way minor API redesigns don't
silently break the watcher.
"""

import json
import logging
import re
import time
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

API_HOST = "apis.cineplex.com"

# Public key served to every visitor inside the cineplex.com web bundle.
# Used only as a first guess; runtime discovery replaces it if rotated.
DEFAULT_SUBSCRIPTION_KEY = "dcdac5601d864addbc2675a2e96cb1f8"

DEFAULT_SHOWTIMES_TEMPLATE = (
    "https://apis.cineplex.com/prod/cpx/theatrical/api/v1/showtimes"
    "?language=en&locationId={locationId}&date={date}"
)

# Per-showtime purchase deep link used by cineplex.com itself; opens seat
# selection on the web and is also understood by the Cineplex mobile app.
DEEPLINK_TEMPLATE = (
    "https://apis.cineplex.com/prod/cpx/theatrical/deeplink"
    "?s={session}&a=0000000001&l={location}&m={slug}&ss=False"
)

BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cineplex.com",
    "Referer": "https://www.cineplex.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


class ShowtimesFetchError(Exception):
    pass


class ShowtimesAuthError(ShowtimesFetchError):
    """401/403 — key rotated or the request needs to come from a browser."""


def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", k.lower())


def build_deeplink(session_id, location_id, movie_slug) -> str:
    return DEEPLINK_TEMPLATE.format(
        session=session_id, location=location_id or "", slug=movie_slug or ""
    )


def format_date_like(sample: str, d: date) -> str:
    """Render date `d` in the same style as the captured sample value."""
    if re.match(r"^\d{4}-\d{2}-\d{2}", sample or ""):
        return d.isoformat()
    if re.match(r"^\d{2}/\d{2}/\d{4}$", sample or ""):
        return f"{d.month:02d}/{d.day:02d}/{d.year}"
    # cineplex.com default: unpadded M/D/YYYY
    return f"{d.month}/{d.day}/{d.year}"


def generalize_showtimes_url(url: str) -> dict:
    """Turn a concrete captured showtimes URL into a reusable template."""
    parts = urlsplit(url)
    qs = parse_qsl(parts.query, keep_blank_values=True)
    date_sample, location_id = None, None
    out = []
    for k, v in qs:
        nk = _norm_key(k)
        if nk == "date":
            date_sample = v
            out.append((k, "{date}"))
        else:
            if "location" in nk and v:
                location_id = v
            out.append((k, v))
    template = urlunsplit(
        (parts.scheme, parts.netloc, parts.path,
         urlencode(out, safe="{}"), "")
    )
    return {
        "template": template,
        "date_sample": date_sample or "",
        "location_id": location_id,
    }


class CineplexClient:
    def __init__(self, config, api_state: dict):
        self.cfg = config
        # persisted across runs: template, headers, location_id, date_sample
        self.api = dict(api_state or {})
        self._rediscovered = False
        self._driver = None
        self.http = requests.Session()
        self.http.headers.update(BROWSER_HEADERS)

    # ---------------------------------------------------------------- config

    @property
    def location_id(self):
        return self.cfg.location_id or self.api.get("location_id")

    def api_state(self) -> dict:
        return self.api

    def _headers(self) -> dict:
        headers = dict(self.api.get("headers") or {})
        if not any(_norm_key(k) == "ocpapimsubscriptionkey" for k in headers):
            headers["Ocp-Apim-Subscription-Key"] = (
                self.cfg.api_key or DEFAULT_SUBSCRIPTION_KEY
            )
        return headers

    def _url_for(self, d: date) -> str:
        template = self.api.get("template")
        if template:
            return template.replace(
                "{date}", format_date_like(self.api.get("date_sample", ""), d)
            )
        if not self.location_id:
            raise ShowtimesFetchError(
                "No locationId known yet. Run discovery (needs Chrome) or set "
                "LOCATION_ID explicitly."
            )
        return DEFAULT_SHOWTIMES_TEMPLATE.format(
            locationId=self.location_id, date=format_date_like("", d)
        )

    # ------------------------------------------------------------- discovery

    def discover(self, force: bool = False) -> bool:
        """Capture the site's own showtimes request (URL + headers)."""
        if self.api.get("template") and not force:
            return True
        from utils.selenium_utils import discover_api_config

        discovered = discover_api_config(
            [self.cfg.theatre_url, self.cfg.movie_url]
        )
        if not discovered:
            logging.warning("API discovery found no showtimes request.")
            return False
        info = generalize_showtimes_url(discovered["url"])
        headers = {
            k: v
            for k, v in discovered.get("headers", {}).items()
            if _norm_key(k) in ("ocpapimsubscriptionkey", "accept", "language")
        }
        self.api.update(
            {
                "template": info["template"],
                "date_sample": info["date_sample"],
                "location_id": info["location_id"] or self.api.get("location_id"),
                "headers": headers,
                "discovered_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        logging.info(
            "Discovered showtimes API: %s (locationId=%s)",
            info["template"], self.api.get("location_id"),
        )
        return True

    # --------------------------------------------------------------- fetches

    def _fetch_requests(self, url: str):
        try:
            resp = self.http.get(url, headers=self._headers(), timeout=30)
        except requests.RequestException as e:
            raise ShowtimesFetchError(f"network error: {e}") from e
        if resp.status_code in (401, 403):
            raise ShowtimesAuthError(f"HTTP {resp.status_code} for {url}")
        if resp.status_code == 404:
            return []  # no showtimes posted for that date
        if resp.status_code != 200:
            raise ShowtimesFetchError(f"HTTP {resp.status_code} for {url}")
        try:
            return resp.json()
        except ValueError as e:
            raise ShowtimesFetchError(f"non-JSON response for {url}") from e

    def _fetch_browser(self, url: str):
        from utils.selenium_utils import browser_fetch_json, build_driver

        if self._driver is None:
            self._driver = build_driver()
            self._driver.get(self.cfg.theatre_url)
            time.sleep(3)
        return browser_fetch_json(self._driver, url, self._headers())

    def fetch_showtimes(self, d: date):
        url = self._url_for(d)
        try:
            return self._fetch_requests(url)
        except ShowtimesAuthError as e:
            logging.warning("Auth/block on showtimes fetch: %s", e)
            if not self._rediscovered:
                self._rediscovered = True
                if self.discover(force=True):
                    try:
                        return self._fetch_requests(self._url_for(d))
                    except ShowtimesAuthError:
                        pass
            logging.info("Falling back to in-browser fetch for %s", d)
            return self._fetch_browser(url)

    def collect_payloads(self, dates):
        """Fetch each date; returns (payloads, failed_dates)."""
        payloads, failed = [], []
        for d in dates:
            try:
                payload = self.fetch_showtimes(d)
                if payload:
                    payloads.append(payload)
            except Exception as e:  # keep going; partial data is useful
                logging.error("Failed to fetch showtimes for %s: %s", d, e)
                failed.append(d)
            time.sleep(self.cfg.request_delay)
        return payloads, failed

    def close(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            finally:
                self._driver = None


# ------------------------------------------------------------------ parsing

_TIME_KEYS = {
    "showstartdatetime", "showstartdate", "starttime", "startdatetime",
    "showtimedatetime", "sessiondatetime", "showdatetime", "showtime",
}
_ID_KEYS = ("vistasessionid", "sessionid", "showtimeid", "presentationid")
_SOLD_OUT_KEYS = ("issoldout", "soldout")
_SEAT_KEYS = ("seatsremaining", "availableseats", "seatsavailable", "seatcount")
_STATUS_KEYS = ("status", "salestatus", "sessionstatus", "showtimestatus")
_NAME_KEYS = ("filmname", "moviename", "name", "title")
_CONTEXT_LABEL_KEYS = ("experience", "attribute", "format", "presentationtype")


def _parse_dt(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S",
                    "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M"):
            try:
                dt = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return dt.replace(tzinfo=None)


_NAMEISH = ("name", "title", "label")


def _is_label(s: str) -> bool:
    s = s.strip()
    return bool(s) and len(s) <= 60 \
        and not s.lower().startswith(("http://", "https://", "/")) \
        and _parse_dt(s) is None


def _label_strings(value):
    """Collect experience labels without leaking across sibling groups.

    Accepts scalar strings, flat lists of strings, and (for shapes like
    ``attributes: [{"name": "IMAX"}]``) name-ish values one level into
    dicts. Deliberately does NOT recurse into nested structures — a
    movie-level ``experiences`` list contains *several* experience groups,
    and recursing would attach every group's labels to every session.
    """
    out = []
    items = value if isinstance(value, list) else [value]
    for item in items:
        if isinstance(item, str) and _is_label(item):
            out.append(item.strip())
        elif isinstance(item, dict):
            for k, v in item.items():
                if _norm_key(k) in _NAMEISH and isinstance(v, str) and _is_label(v):
                    out.append(v.strip())
    return out


def _first_time(node: dict):
    for k, v in node.items():
        if _norm_key(k) in _TIME_KEYS:
            dt = _parse_dt(v)
            if dt is not None:
                return dt
    return None


def _looks_like_session(node: dict) -> bool:
    norm = {_norm_key(k) for k in node}
    if norm & set(_ID_KEYS + _SOLD_OUT_KEYS + _SEAT_KEYS):
        return True
    # grouping nodes (a date wrapping movies, an experience wrapping
    # sessions) carry non-empty list children; leaf sessions don't
    return not any(isinstance(v, list) and v for v in node.values())


def _sold_out(node: dict):
    for k, v in node.items():
        nk = _norm_key(k)
        if nk in _SOLD_OUT_KEYS and isinstance(v, bool):
            return v
        if nk in _STATUS_KEYS and isinstance(v, str) and "sold" in v.lower():
            return True
    for k, v in node.items():
        if _norm_key(k) in _SEAT_KEYS and isinstance(v, int):
            return v <= 0
    return False


def _seats(node: dict):
    for k, v in node.items():
        if _norm_key(k) in _SEAT_KEYS and isinstance(v, int):
            return v
    return None


def _session_id(node: dict):
    for wanted in _ID_KEYS + ("id",):
        for k, v in node.items():
            if _norm_key(k) == wanted and isinstance(v, (int, str)) and str(v):
                return str(v)
    return None


def _own_deeplink(node: dict):
    for k, v in node.items():
        if "deeplink" in _norm_key(k) and isinstance(v, str) and v.startswith("http"):
            return v
    return None


def extract_sessions(payload) -> list:
    """Walk arbitrary showtimes JSON and pull out individual sessions."""
    sessions = []

    def walk(node, ctx):
        if isinstance(node, list):
            for item in node:
                walk(item, ctx)
            return
        if not isinstance(node, dict):
            return

        new_ctx = dict(ctx)
        for k, v in node.items():
            nk = _norm_key(k)
            if nk in _NAME_KEYS and isinstance(v, str) and v.strip():
                if "movie_name" not in new_ctx or nk in ("filmname", "moviename"):
                    new_ctx["movie_name"] = v.strip()
            if isinstance(v, str) and "/movie/" in v:
                new_ctx["movie_url"] = v
            if nk == "locationid" and isinstance(v, (int, str)) and str(v):
                new_ctx["location_id"] = str(v)

        labels = set(ctx.get("labels", ()))
        for k, v in node.items():
            nk = _norm_key(k)
            if any(t in nk for t in _CONTEXT_LABEL_KEYS):
                labels.update(_label_strings(v))
        new_ctx["labels"] = tuple(sorted(labels))

        start = _first_time(node)
        if start is not None and _looks_like_session(node):
            sid = _session_id(node)
            sessions.append(
                {
                    "key": sid or f"{start.isoformat()}|{'|'.join(new_ctx['labels'])}",
                    "session_id": sid,
                    "start": start.isoformat(),
                    "date": start.date().isoformat(),
                    "time": start.strftime("%I:%M %p").lstrip("0"),
                    "movie": new_ctx.get("movie_name", ""),
                    "movie_url": new_ctx.get("movie_url", ""),
                    "experiences": list(new_ctx["labels"]),
                    "sold_out": _sold_out(node),
                    "seats": _seats(node),
                    "deeplink": _own_deeplink(node),
                    "location_id": new_ctx.get("location_id", ""),
                }
            )

        for v in node.values():
            walk(v, new_ctx)

    walk(payload, {})

    unique = {}
    for s in sessions:
        unique.setdefault(s["key"], s)
    return list(unique.values())


def filter_sessions(sessions, film_keyword, experience_keywords) -> list:
    """Keep sessions for the right film and experience (e.g. IMAX 70mm)."""
    out = []
    film_kw = (film_keyword or "").lower()
    exp_kws = [k.strip().lower().replace(" ", "") for k in experience_keywords if k.strip()]
    unlabeled_matches = 0
    for s in sessions:
        haystack = f"{s.get('movie', '')} {s.get('movie_url', '')}".lower()
        if film_kw and film_kw not in haystack:
            continue
        blob = "".join(s.get("experiences") or []).lower().replace(" ", "")
        if exp_kws:
            if not blob:
                unlabeled_matches += 1
                continue
            if not all(kw in blob for kw in exp_kws):
                continue
        out.append(s)
    if unlabeled_matches:
        logging.warning(
            "%d session(s) matched the film but carried no experience labels; "
            "if alerts seem to be missing, unset EXPERIENCE_KEYWORDS to see "
            "everything.", unlabeled_matches,
        )
    return out
