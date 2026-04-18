# CineAlert - Claude Code Context

## Project Overview
CineAlert is a Dockerized Python app that monitors Cineplex.com for IMAX 70mm ticket availability at Cineplex Cinemas Vaughan and sends SMS alerts via email-to-SMS (Gmail SMTP).

Forked from: github.com/CreatorSky/cineplex-notifier (MIT)
Repo: https://github.com/rahulkahani/cinealert.git

## Target Movies
- **The Odyssey** — slug: `the-odyssey`, ID: 37617, release: July 17, 2026 (Nolan)
- **Dune: Part 3** — slug: `dune-part-3`, ID: 37998, release: Dec 18, 2026 (Villeneuve)

## Target Theatre
Cineplex Cinemas Vaughan — 3555 Highway 7 West, Vaughan, ON

## Target Format
IMAX 70mm — requires BOTH `vistaAttribute: "IMAX"` AND `vistaAttribute: "70MM"` on a showtime

## File Structure
```
cinealert/
  main.py              # Entry point, orchestration loop
  config.json          # Movie list, theatre, format, phone config
  state.json           # Auto-generated alert state (git-ignored)
  utils/
    scraper.py         # Fetches Cineplex page, extracts __NEXT_DATA__
    alert.py           # Composes and sends SMS via email-to-SMS
    state.py           # Reads/writes state.json for duplicate prevention
  providers/
    sms_gateways.py    # Canadian carrier SMS gateway domains
  Dockerfile           # Lightweight Python image (NO Chrome/Selenium)
  docker-compose.yml   # Container config with volume mount
  Makefile             # build, run, stop, purge commands
  entrypoint.sh        # Loads env vars and starts cron
  run.sh               # Cron-invoked script that calls main.py
  requirements.txt     # requests, beautifulsoup4
```

## Tech Stack
- Python 3.10+
- `requests` for HTTP
- `beautifulsoup4` for HTML parsing
- `smtplib` (stdlib) for Gmail SMTP
- Linux cron inside Docker for scheduling (every 15 min)
- JSON files for config and state

## Key Technical Details

### Cineplex Data Extraction
- Cineplex uses Next.js — each movie page has `<script id="__NEXT_DATA__">` with JSON
- Data path: `props.pageProps.movieDetails`
- Key fields: `.formats` (array of int IDs), `.hasShowtimes`, `.name`, `.slug`

### Format Detection (Two Stages)
1. **Format Watch**: Check `movieDetails.formats` array for IMAX/70mm format IDs appearing
2. **Showtime Watch**: Check for actual showtimes at Vaughan with both IMAX + 70MM experience tags

### SMS Alert Template
```
TICKETS LIVE: [Movie Name]
IMAX 70mm @ Cineplex Vaughan
Tickets are selling fast - book now before they sell out!
[Direct Purchase URL]
```
Must be plain text, under 320 chars, no HTML.

### Environment Variables (set in docker-compose.yml)
- `EMAIL` — Gmail sender address
- `PASSWORD` — Gmail app password
- `PHONE` — Phone/carrier pairs, comma-separated (e.g., `5551234567:Rogers,5559876543:Bell`)

## Conventions
- Use snake_case for all Python files and variables
- JSON config keys use snake_case
- Logging: use Python `logging` module, write to `/app/logs/main.log`
- 30-second timeout on all HTTP requests
- Add random delay (0-60s) before requests to avoid exact polling intervals
- Realistic User-Agent header on all requests
- Graceful error handling: log and continue to next movie, never crash the loop
- State tracking keyed by `movie_slug:alert_type`

## Docker
- Base image: `python:3.10-slim`
- No Chrome/Selenium — pure HTTP + parsing
- state.json mounted as Docker volume for persistence across restarts
- Cron schedule: `*/15 * * * *`

## Development Commands
```bash
make build    # Build Docker image
make run      # Start container (detached)
make stop     # Stop container
make purge    # Remove container and image
```

## Testing Checklist
- [ ] Scraper works against live Cineplex pages for both movies
- [ ] SMS delivery reaches phone
- [ ] Duplicate prevention works across runs
- [ ] Error handling with invalid URLs / network failures
- [ ] Docker build and run cycle works
