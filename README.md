# CineAlert — Cineplex showtime release watcher

Watches Cineplex for **new showtime releases** and **seats coming back on
sold-out shows**, and alerts you within minutes. Configured out of the box
for **Dune: Part Three in IMAX 70mm at Cineplex Cinemas Vaughan**
(opens Dec 18, 2026 — the first wave of 70mm showtimes sold out almost
instantly, and more dates are expected to drop without warning).

## How it works

Every **5 minutes** (cron inside the container):

1. Queries the same showtimes API the cineplex.com website uses
   (`apis.cineplex.com`), for every date in your watch window. The API URL,
   subscription key and theatre `locationId` are **auto-discovered** on the
   first run by loading the theatre page in headless Chrome and capturing
   the network call the page makes — so key rotations or ID changes heal
   themselves. If plain API calls ever get blocked, it falls back to
   fetching from inside the browser page.
2. Keeps only sessions matching your film (`FILM_KEYWORD=dune`) and
   experience (`EXPERIENCE_KEYWORDS=70mm`, which matches "IMAX 70MM FILM").
3. Diffs against the previous run (state is persisted in `./state`):
   - **new showtimes released** → alert
   - **previously sold-out show has seats again** → alert
   - nothing changed → stays silent
4. Alerts carry a **direct booking deep link per showtime** that opens the
   seat-selection page on cineplex.com (and is understood by the Cineplex
   app on phones):
   `https://apis.cineplex.com/prod/cpx/theatrical/deeplink?s=<session>&a=0000000001&l=<location>&m=dune-part-three&ss=False`

On its very first successful run it emails you a **baseline** listing the
currently posted 70mm showtimes (even the sold-out ones) — that's your
end-to-end confirmation that detection works.

If every fetch fails 3 runs in a row it sends you an ops alert instead of
dying silently.

## Alert channels

- **ntfy push (recommended — this is the "on the minute" channel):**
  install the [ntfy](https://ntfy.sh) app, subscribe to a topic you invent
  (make it unguessable, e.g. `dune3-rk-x8k2p9`), set `NTFY_TOPIC` to it.
  Tapping the notification opens the booking link directly.
- **Email:** set `EMAIL` (Gmail) + `PASSWORD`
  ([Gmail app password](https://support.google.com/accounts/answer/185833),
  not your normal password). `EMAIL_TO` defaults to the sender.
- **SMS (best-effort):** `PHONE=4165551234:Telus` via carrier
  email-to-SMS gateways. Canadian carriers have been retiring these
  (Rogers/Fido are unreliable) — treat ntfy push as primary.
  Supported: Virgin, Bell, MTS, Rogers, Telus, Fido, Freedom, Koodo, PC,
  Sasktel.

## Quick start

```bash
# 1. edit the environment block in docker-compose.yml (EMAIL, PASSWORD, NTFY_TOPIC)
make build
make run          # starts the container; first check runs immediately

# 2. verify the alert pipeline end-to-end (sends a real test alert):
docker compose run --rm cinealert python /app/main.py --test-alert

# 3. watch it work
tail -f logs/main.log
```

## Configuration (docker-compose.yml)

| Variable | Default | Meaning |
| --- | --- | --- |
| `MOVIE_URL` | dune-part-three page | Cineplex movie page (used in alerts + discovery) |
| `THEATRE_URL` | cineplex-cinemas-vaughan page | theatre to watch (drives API discovery) |
| `FILM_KEYWORD` | `dune` | substring the film name must contain |
| `EXPERIENCE_KEYWORDS` | `70mm` | comma list; every keyword must appear in the session's experience labels. Empty = all formats |
| `WATCH_FROM` / `WATCH_TO` | `2026-12-18` / `2027-01-03` | show dates to scan |
| `EMAIL` / `PASSWORD` / `EMAIL_TO` | — | Gmail sender / app password / recipients |
| `NTFY_TOPIC` | — | ntfy.sh push topic |
| `PHONE` | — | `number:provider,...` (optional) |
| `LOCATION_ID` / `CPX_API_KEY` | auto | manual overrides if you ever want to skip discovery |

## Debugging

```bash
# force API re-discovery (e.g. after Cineplex changes something):
docker compose run --rm cinealert python /app/main.py --discover --dry-run

# dump the raw API payloads to state/last_payloads.json:
docker compose run --rm cinealert python /app/main.py --dump-raw --dry-run

# replay a saved payload through the detection logic without network:
python main.py --simulate tests/fixture_showtimes.json --dry-run
```

## Useful links (Dune 3 / Vaughan)

- Movie page: <https://www.cineplex.com/movie/dune-part-three>
- Theatre page: <https://www.cineplex.com/theatre/cineplex-cinemas-vaughan>
- IMAX's own listing for the same screen:
  <https://www.imax.com/theatre/cineplex-cinemas-vaughan-imax/dune-part-three>

## License

MIT.
