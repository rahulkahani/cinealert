"""CineAlert — watches Cineplex for new/available showtimes and alerts you.

Built for: Dune: Part Three in IMAX 70mm at Cineplex Cinemas Vaughan.

Each run (cron fires one every 5 minutes):
  1. queries the Cineplex showtimes API for every date in the watch window;
  2. keeps only sessions for the watched film + experience (e.g. "70mm");
  3. compares against the previous run's state and alerts on
       - brand new showtimes (new dates released), and
       - previously sold-out showtimes that now have seats;
  4. sends alerts via email, ntfy push, and email-to-SMS, each with links
     that open the Cineplex site/app directly on the booking page.
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from utils import state as state_store
from utils.cineplex_api import (
    CineplexClient,
    build_deeplink,
    extract_sessions,
    filter_sessions,
)
from utils.email_utils import send_email, send_ntfy, send_sms

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

OPS_ALERT_AFTER_FAILURES = 3
OPS_ALERT_COOLDOWN_HOURS = 6


def _load_file_config(state_dir: str) -> dict:
    """Settings saved by the web UI (state/config.json)."""
    try:
        with open(os.path.join(state_dir, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return {}


class Config:
    def __init__(self, args):
        env = os.environ.get
        self.state_dir = env("STATE_DIR", os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "state"))
        file_cfg = _load_file_config(self.state_dir)

        def pick(arg_val, key, default=""):
            """CLI flag > web-UI config.json > environment > default.

            A key present-but-empty in config.json is an explicit 'unset'
            (the UI cleared it) and does NOT fall through to the env.
            Values containing '<' are docker-compose placeholders.
            """
            if arg_val:
                return str(arg_val).strip()
            if key in file_cfg:
                v = str(file_cfg[key] or "").strip()
                return v if "<" not in v else ""
            v = env(key, "")
            return v.strip() if v and "<" not in v else default

        self.movie_url = pick(args.url, "MOVIE_URL") or env("URL", "").strip() or \
            "https://www.cineplex.com/movie/dune-part-three"
        self.theatre_url = pick(args.theatre_url, "THEATRE_URL") or \
            "https://www.cineplex.com/theatre/cineplex-cinemas-vaughan"
        self.film_keyword = pick(args.film_keyword, "FILM_KEYWORD", "dune")
        self.experience_keywords = [
            k for k in pick(args.experience, "EXPERIENCE_KEYWORDS", "70mm").split(",")
            if k.strip()
        ]
        self.watch_from = date.fromisoformat(
            pick(args.watch_from, "WATCH_FROM") or "2026-12-18")
        self.watch_to = date.fromisoformat(
            pick(args.watch_to, "WATCH_TO") or "2027-01-03")
        self.timezone = env("TZ_NAME", "America/Toronto")

        self.email = pick(args.email, "EMAIL")
        self.password = pick(args.password, "PASSWORD")
        self.email_to = [
            e.strip()
            for e in (pick(args.email_to, "EMAIL_TO") or self.email).split(",")
            if e.strip()
        ]
        self.phone_pairs = [
            p.strip() for p in pick(args.phone, "PHONE").split(",") if p.strip()
        ]
        self.ntfy_topic = pick(args.ntfy_topic, "NTFY_TOPIC")
        self.ntfy_email = pick(None, "NTFY_EMAIL")
        self.use_deeplinks = pick(None, "USE_DEEPLINKS", "true").lower() \
            in ("1", "true", "yes", "on")

        self.location_id = pick(None, "LOCATION_ID")
        self.api_key = pick(None, "CPX_API_KEY")
        self.movie_slug = env("MOVIE_SLUG", "") or \
            self.movie_url.rstrip("/").rsplit("/", 1)[-1]
        self.request_delay = float(env("REQUEST_DELAY", "0.5"))

    def validate(self, need_credentials=True):
        if not self.movie_url.startswith("https://www.cineplex.com"):
            raise ValueError("MOVIE_URL must be a https://www.cineplex.com URL.")
        if self.watch_to < self.watch_from:
            raise ValueError("WATCH_TO is before WATCH_FROM.")
        if need_credentials and not (self.email and self.password) and not self.ntfy_topic:
            raise ValueError(
                "No alert channel configured: set NTFY_TOPIC (no account "
                "needed) and/or EMAIL + PASSWORD (Gmail app password)."
            )


def parse_args(argv):
    p = argparse.ArgumentParser(description="Cineplex showtime release watcher")
    p.add_argument("--url", "-u", help="Cineplex movie URL")
    p.add_argument("--theatre-url", help="Cineplex theatre URL to watch")
    p.add_argument("--film-keyword", help="substring that must appear in the film name")
    p.add_argument("--experience", help="comma list, e.g. '70mm' or 'imax,70mm'")
    p.add_argument("--watch-from", help="first show date to watch (YYYY-MM-DD)")
    p.add_argument("--watch-to", help="last show date to watch (YYYY-MM-DD)")
    p.add_argument("--email", "-e", help="Gmail address used to send alerts")
    p.add_argument("--password", "-p", help="Gmail app password")
    p.add_argument("--email-to", help="comma list of alert recipients (default: sender)")
    p.add_argument("--phone", help="number:provider pairs, comma separated (optional)")
    p.add_argument("--ntfy-topic", help="ntfy.sh topic for push notifications")
    p.add_argument("--test-alert", action="store_true",
                   help="send a test alert through every channel and exit")
    p.add_argument("--discover", action="store_true",
                   help="force re-discovery of the showtimes API config")
    p.add_argument("--simulate", metavar="FILE",
                   help="parse a saved showtimes JSON file instead of the network")
    p.add_argument("--dump-raw", action="store_true",
                   help="save raw API payloads under the state dir for debugging")
    p.add_argument("--dry-run", action="store_true",
                   help="print alerts instead of sending them")
    return p.parse_args(argv)


def watch_dates(cfg):
    today = datetime.now(ZoneInfo(cfg.timezone)).date()
    start = max(cfg.watch_from, today)
    return [start + timedelta(days=i) for i in range((cfg.watch_to - start).days + 1)]


def booking_link(session, cfg, location_id):
    if not cfg.use_deeplinks:
        return cfg.movie_url
    if session.get("deeplink"):
        return session["deeplink"]
    location = session.get("location_id") or location_id
    if session.get("session_id") and location:
        return build_deeplink(session["session_id"], location, cfg.movie_slug)
    return cfg.movie_url


def format_sessions(sessions, cfg, location_id):
    lines = []
    for s in sorted(sessions, key=lambda x: x["start"]):
        day = datetime.fromisoformat(s["start"]).strftime("%a %b %d, %Y")
        exp = ", ".join(s["experiences"]) or "unlabeled"
        if s["sold_out"]:
            lines.append(f"• {day} — {s['time']} ({exp}) — ❌ SOLD OUT")
            lines.append("  (no seats right now — you'll get a SEATS BACK "
                         "alert if any free up)")
        else:
            status = (f"{s['seats']} seats left" if s.get("seats") is not None
                      else "seats available")
            lines.append(f"• {day} — {s['time']} ({exp}) — ✅ {status}")
            lines.append(f"  Book now: {booking_link(s, cfg, location_id)}")
    return "\n".join(lines)


def best_click_url(sessions, cfg, location_id):
    """Deep link of the earliest bookable session, else the movie page."""
    available = [s for s in sorted(sessions, key=lambda x: x["start"])
                 if not s["sold_out"]]
    if available:
        return booking_link(available[0], cfg, location_id)
    return cfg.movie_url


def dates_summary(sessions):
    days = sorted({s["date"] for s in sessions})
    return ", ".join(datetime.fromisoformat(d).strftime("%b %d") for d in days)


def send_all(cfg, subject, body, sms_text, click_url, dry_run,
             include_sms=True):
    if dry_run:
        print(f"\n=== DRY RUN ALERT ===\nSubject: {subject}\n\n{body}\n"
              f"\nSMS: {sms_text}\nClick: {click_url}\n")
        return True
    sent = False
    if cfg.ntfy_topic:
        sent |= send_ntfy(cfg.ntfy_topic, subject, body, click_url,
                          email=cfg.ntfy_email)
    if cfg.email and cfg.password:
        sent |= send_email(cfg.email, cfg.password, cfg.email_to, subject, body)
        if include_sms and cfg.phone_pairs:
            sent |= send_sms(cfg.email, cfg.password, cfg.phone_pairs, sms_text)
    return sent


def handle_total_failure(cfg, st, dry_run):
    health = st.setdefault("health", {})
    health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
    n = health["consecutive_failures"]
    logging.error("All showtime fetches failed (%d consecutive run(s)).", n)
    last = health.get("last_ops_alert")
    cooled_down = True
    if last:
        elapsed = datetime.now() - datetime.fromisoformat(last)
        cooled_down = elapsed > timedelta(hours=OPS_ALERT_COOLDOWN_HOURS)
    if n >= OPS_ALERT_AFTER_FAILURES and cooled_down:
        send_all(
            cfg,
            "CineAlert is failing — check it",
            f"CineAlert could not fetch Cineplex showtimes for {n} runs in a "
            f"row. It may be blocked or the API may have changed.\n"
            f"Check the container logs (docker compose logs) and the state "
            f"dir.\nWatched movie: {cfg.movie_url}",
            f"CineAlert failing for {n} runs - check logs",
            cfg.movie_url,
            dry_run,
            include_sms=False,
        )
        health["last_ops_alert"] = datetime.now().isoformat(timespec="seconds")


def run_test_alert(cfg, dry_run):
    subject = "TEST — CineAlert pipeline works"
    body = (
        "This is a test alert from CineAlert.\n\n"
        f"Watching: {cfg.film_keyword!r} with experience {cfg.experience_keywords} "
        f"from {cfg.watch_from} to {cfg.watch_to}\n"
        f"Movie page: {cfg.movie_url}\n"
        f"Theatre page: {cfg.theatre_url}\n\n"
        "If you received this by email/push/SMS, alerts will reach you when "
        "real showtimes drop."
    )
    ok = send_all(cfg, subject, body,
                  "TEST CineAlert works. " + cfg.movie_url,
                  cfg.movie_url, dry_run)
    print("Test alert sent." if ok else "Test alert FAILED — check logs above.")
    return 0 if ok else 1


def main(argv=None):
    args = parse_args(argv)
    cfg = Config(args)
    cfg.validate(need_credentials=not (args.dry_run or args.simulate))

    if args.test_alert:
        return run_test_alert(cfg, args.dry_run)

    st = state_store.load(cfg.state_dir)
    client = None

    if args.simulate:
        with open(args.simulate, "r", encoding="utf-8") as f:
            payloads = [json.load(f)]
        failed = []
        location_id = cfg.location_id or st.get("api", {}).get("location_id", "")
    else:
        client = CineplexClient(cfg, st.get("api", {}))
        if args.discover or not st.get("api", {}).get("template"):
            client.discover(force=args.discover)
        dates = watch_dates(cfg)
        if not dates:
            logging.info("Watch window %s..%s is in the past; nothing to do.",
                         cfg.watch_from, cfg.watch_to)
            return 0
        logging.info("Checking %d date(s): %s .. %s",
                     len(dates), dates[0], dates[-1])
        payloads, failed = client.collect_payloads(dates)
        st["api"] = client.api_state()
        location_id = client.location_id or ""
        if args.dump_raw:
            os.makedirs(cfg.state_dir, exist_ok=True)
            dump_path = os.path.join(cfg.state_dir, "last_payloads.json")
            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(payloads, f, indent=2)
            logging.info("Raw payloads dumped to %s", dump_path)

    try:
        if not payloads and failed:
            handle_total_failure(cfg, st, args.dry_run)
            state_store.save(cfg.state_dir, st)
            return 1
        st.setdefault("health", {})["consecutive_failures"] = 0

        sessions = []
        for payload in payloads:
            sessions.extend(extract_sessions(payload))
        matched = filter_sessions(sessions, cfg.film_keyword, cfg.experience_keywords)
        logging.info("Extracted %d session(s); %d match film=%r experience=%s",
                     len(sessions), len(matched), cfg.film_keyword,
                     cfg.experience_keywords)

        known = st.setdefault("sessions", {})
        new = [s for s in matched if s["key"] not in known]
        freed = [
            s for s in matched
            if s["key"] in known and known[s["key"]].get("sold_out") and not s["sold_out"]
        ]

        now_iso = datetime.now().isoformat(timespec="seconds")
        if not st.get("initialized"):
            body = (
                f"CineAlert is now watching {cfg.movie_url}\n"
                f"Theatre: {cfg.theatre_url}\n"
                f"Experience filter: {cfg.experience_keywords}, "
                f"dates {cfg.watch_from} → {cfg.watch_to}\n\n"
                f"Current matching showtimes ({len(matched)}):\n"
                f"{format_sessions(matched, cfg, location_id) or '(none posted yet)'}\n\n"
                "You will be alerted the moment new dates are released or a "
                "sold-out show gets seats back."
            )
            send_all(cfg, "CineAlert armed — baseline established", body,
                     "", cfg.movie_url, args.dry_run, include_sms=False)
            st["initialized"] = True
        elif new or freed:
            parts, bits = [], []
            if new:
                parts.append(f"🚨 NEW SHOWTIMES RELEASED ({len(new)}):\n"
                             f"{format_sessions(new, cfg, location_id)}")
                plural = "s" if len(new) != 1 else ""
                bits.append(f"{len(new)} new showtime{plural} ({dates_summary(new)})")
            if freed:
                parts.append(f"🎟️ SEATS BACK ON SOLD-OUT SHOWS ({len(freed)}):\n"
                             f"{format_sessions(freed, cfg, location_id)}")
                plural = "s" if len(freed) != 1 else ""
                bits.append(f"seats back on {len(freed)} sold-out "
                            f"show{plural} ({dates_summary(freed)})")
            summary = " & ".join(bits)
            subject = f"DUNE 3 IMAX 70mm @ Vaughan: {summary}"
            click = best_click_url(new + freed, cfg, location_id)
            body = "\n\n".join(parts) + (
                f"\n\nAll showtimes / backup link: {cfg.movie_url}"
                f"\nTheatre page: {cfg.theatre_url}"
                f"\nGO GO GO — these sell out in minutes."
            )
            sms = f"DUNE3 70mm Vaughan: {summary}. {click}"
            send_all(cfg, subject, body, sms, click, args.dry_run)
        else:
            logging.info("No changes — %d matching session(s) already known.",
                         len(matched))

        for s in matched:
            entry = known.setdefault(s["key"], {"first_seen": now_iso})
            entry.update({
                "sold_out": s["sold_out"],
                "start": s["start"],
                "last_seen": now_iso,
                "experiences": s["experiences"],
            })

        state_store.save(cfg.state_dir, st)
        return 0
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
