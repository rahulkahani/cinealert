# Plan: Complete Phase 2 Testing & Prepare for Deployment

## Context
Phase 1 (core build) is done and pushed to GitHub. The scraper successfully fetches both movie pages from live Cineplex. We found two issues during testing that need fixing, and the user needs help setting up SMS credentials before we can finish Phase 2 testing.

## Steps

### 1. Fix Python 3.9 compatibility
- `utils/scraper.py` — already has `from __future__ import annotations` (done in testing)
- `utils/alert.py` line 74 — `list[tuple[str, str]]` needs the same fix

### 2. Switch credentials to `.env` file (security)
`.env` is already gitignored but `docker-compose.yml` is NOT — and it has credential placeholders. Fix:
- Update `docker-compose.yml` to reference a `.env` file via `env_file: .env`
- Remove hardcoded env values from `docker-compose.yml`
- Create a `.env.example` with placeholder values for reference
- User creates `.env` locally with real credentials (never committed)

### 3. User: Set up Gmail App Password
1. Go to myaccount.google.com → Security → 2-Step Verification (enable if not already)
2. Scroll to bottom → App passwords → Create one named "CineAlert"
3. Copy the 16-character password
4. Create `.env` file with:
   ```
   EMAIL=your-email@gmail.com
   PASSWORD=xxxx-xxxx-xxxx-xxxx
   PHONE=your10digitnumber:Rogers
   ```

### 4. Test SMS delivery
- Set env vars and run a quick send test to verify SMS arrives on phone

### 5. Test duplicate prevention
- Run `main.py` twice — confirm `state.json` prevents duplicate alerts on second run

### 6. Docker build & run
- `make build` → `make run` → `make logs` → verify it works
- `make stop` to clean up

## Files to modify
- `utils/scraper.py` — already fixed, needs commit
- `utils/alert.py` — add `from __future__ import annotations`
- `docker-compose.yml` — use `env_file: .env`, remove hardcoded credentials
- `.env.example` — new file with placeholder values

## Verification
1. Scraper parses both movie pages (already confirmed)
2. SMS arrives on user's Rogers phone
3. Second run produces no duplicate alert
4. Docker builds and runs cleanly
5. No credentials in git
