"""CineAlert config UI — a small local web page so you never edit files.

Runs inside the container on port 8080 (http://localhost:8080). Settings
are written to state/config.json, which main.py reads on every check
(precedence: CLI flags > this file > docker-compose environment).

This is meant for your home network only — it has no login. Don't port-
forward it to the internet.
"""

import json
import os
import subprocess
import sys
from datetime import datetime

from flask import Flask, redirect, render_template_string, request

from providers.sms_gateways import sms_gateways

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.environ.get("STATE_DIR", os.path.join(APP_DIR, "state"))
CONFIG_PATH = os.path.join(STATE_DIR, "config.json")
STATE_PATH = os.path.join(STATE_DIR, "state.json")
LOG_PATH = os.environ.get("LOG_PATH", os.path.join(APP_DIR, "logs", "main.log"))

app = Flask(__name__)

FIELDS = [
    ("NTFY_TOPIC", "ntfy push topic — the easy, no-password channel: install "
     "the free ntfy app, subscribe to a topic you invent (make it "
     "unguessable), type the same topic here", "dune3-rk-x8k2p9", "text"),
    ("NTFY_EMAIL", "Also send alerts to this email via ntfy (optional — no "
     "Gmail password needed; limited to a few emails/day, fine for alerts)",
     "you@gmail.com", "email"),
    ("EMAIL", "OPTIONAL Gmail sender — only needed for SMS texts or "
     "unlimited email. Leave empty if ntfy above is enough", "you@gmail.com",
     "email"),
    ("PASSWORD", "OPTIONAL Gmail app password — a separate, revocable "
     "16-character code, NOT your Gmail password "
     "(myaccount.google.com → Security → App passwords)",
     "abcd efgh ijkl mnop", "password"),
    ("EMAIL_TO", "Send alert emails to (comma separated; empty = same as "
     "the Gmail sender)", "", "text"),
    ("PHONE", "Text message (SMS): number:Provider pairs, comma separated "
     "(needs the Gmail fields above)", "4165551234:Telus", "text"),
    ("WATCH_FROM", "Earliest SHOW date you'd attend (YYYY-MM-DD). These are "
     "movie dates, not release dates — the watcher itself checks 24/7 from "
     "now on, so whenever tickets drop, you're covered", "2026-12-18", "text"),
    ("WATCH_TO", "Latest SHOW date you'd attend (YYYY-MM-DD)", "2027-01-03",
     "text"),
    ("FILM_KEYWORD", "Film name must contain", "dune", "text"),
    ("EXPERIENCE_KEYWORDS", "Format must contain (comma separated; empty = "
     "every format)", "70mm", "text"),
    ("MOVIE_URL", "Cineplex movie page",
     "https://www.cineplex.com/movie/dune-part-three", "text"),
    ("THEATRE_URL", "Cineplex theatre page",
     "https://www.cineplex.com/theatre/cineplex-cinemas-vaughan", "text"),
]

PAGE = """
<!doctype html>
<title>CineAlert</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 760px;
         margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }
  h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; margin-top: 2rem; }
  label { display: block; margin-top: .9rem; font-weight: 600; font-size: .9rem; }
  .hint { font-weight: 400; opacity: .7; display: block; font-size: .8rem; }
  input[type=text], input[type=email], input[type=password] {
    width: 100%; padding: .5rem; margin-top: .25rem; box-sizing: border-box;
    border: 1px solid #8884; border-radius: 6px; font-size: .95rem; }
  .row { display: flex; gap: .6rem; margin-top: 1.4rem; flex-wrap: wrap; }
  button { padding: .55rem 1.1rem; border-radius: 6px; border: 1px solid #8886;
           cursor: pointer; font-size: .95rem; }
  button.primary { background: #2563eb; color: white; border: none; }
  .msg { padding: .7rem 1rem; border-radius: 6px; margin: 1rem 0;
         background: #16a34a22; border: 1px solid #16a34a55; white-space: pre-wrap; }
  .msg.err { background: #dc262622; border-color: #dc262655; }
  .status { background: #8881; border-radius: 8px; padding: .8rem 1rem;
            font-size: .9rem; }
  pre { background: #8881; padding: .8rem; border-radius: 8px; overflow-x: auto;
        font-size: .78rem; max-height: 300px; }
  .check { margin-top: 1rem; font-size: .9rem; }
</style>
<h1>🎬 CineAlert — Dune 3 IMAX 70mm watcher</h1>

{% if message %}<div class="msg {{ 'err' if error else '' }}">{{ message }}</div>{% endif %}

<div class="status">
  <b>Status:</b> {{ status.armed }}<br>
  <b>Last check:</b> {{ status.last_check }}<br>
  <b>Showtimes being tracked:</b> {{ status.tracked }}<br>
  <b>Consecutive fetch failures:</b> {{ status.failures }}
</div>

<form method="post" action="/save">
  {% for key, label, placeholder, kind in fields %}
    <label>{{ label }}
      <span class="hint">{{ key }}</span>
      <input type="{{ kind }}" name="{{ key }}" value="{{ values[key] }}"
             placeholder="{{ placeholder }}">
    </label>
  {% endfor %}
  <div class="check">
    <label style="font-weight:400">
      <input type="checkbox" name="USE_DEEPLINKS" {{ 'checked' if deeplinks }}>
      Use per-showtime booking deep links in alerts (uncheck to always link
      the plain cineplex.com movie page instead)
    </label>
  </div>
  <div class="hint" style="margin-top:.8rem">
    SMS providers supported: {{ providers }}. Carrier SMS gateways are
    best-effort — the ntfy push is the fast, reliable channel.
  </div>
  <div class="row">
    <button class="primary" type="submit">💾 Save settings</button>
  </div>
</form>

<div class="row">
  <form method="post" action="/test">
    <button type="submit">📨 Send test alert (all channels)</button>
  </form>
  <form method="post" action="/check">
    <button type="submit">🔄 Run a check right now</button>
  </form>
</div>

<h2>Recent log</h2>
<pre>{{ log }}</pre>
"""


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return {}


def current_values():
    cfg = load_config()
    values = {}
    for key, *_ in FIELDS:
        if key in cfg:
            values[key] = str(cfg[key] or "")
        else:
            v = os.environ.get(key, "")
            values[key] = "" if "<" in v else v
    return values


def read_status():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            st = json.load(f)
        mtime = datetime.fromtimestamp(os.path.getmtime(STATE_PATH))
        last = mtime.strftime("%Y-%m-%d %H:%M:%S")
    except (FileNotFoundError, ValueError, OSError):
        st, last = {}, "never (no run has completed yet)"
    return {
        "armed": "✅ armed — baseline established"
                 if st.get("initialized") else "⏳ waiting for first successful check",
        "last_check": last,
        "tracked": len(st.get("sessions", {})),
        "failures": st.get("health", {}).get("consecutive_failures", 0),
    }


def read_log(lines=40):
    try:
        with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:]) or "(log is empty)"
    except OSError:
        return "(no log yet)"


def render(message="", error=False):
    return render_template_string(
        PAGE,
        fields=FIELDS,
        values=current_values(),
        deeplinks=str(load_config().get("USE_DEEPLINKS",
                                        os.environ.get("USE_DEEPLINKS", "true")))
        .lower() in ("1", "true", "yes", "on"),
        providers=", ".join(sorted(k for k in sms_gateways if k != "Koodoo")),
        status=read_status(),
        log=read_log(),
        message=message,
        error=error,
    )


@app.get("/")
def index():
    return render()


@app.post("/save")
def save():
    cfg = load_config()
    for key, *_ in FIELDS:
        cfg[key] = request.form.get(key, "").strip()
    cfg["USE_DEEPLINKS"] = "true" if request.form.get("USE_DEEPLINKS") else "false"
    for key in ("WATCH_FROM", "WATCH_TO"):
        if cfg[key]:
            try:
                datetime.strptime(cfg[key], "%Y-%m-%d")
            except ValueError:
                return render(f"{key} must look like 2026-12-18 "
                              f"(got {cfg[key]!r}). Nothing was saved.", error=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return render("Saved. The next check (within 5 minutes) uses these "
                  "settings. Now hit “Send test alert” to confirm they work.")


def run_main(*args, timeout=180):
    proc = subprocess.run(
        [sys.executable, os.path.join(APP_DIR, "main.py"), *args],
        capture_output=True, text=True, timeout=timeout, cwd=APP_DIR,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


@app.post("/test")
def test_alert():
    try:
        code, out = run_main("--test-alert")
    except subprocess.TimeoutExpired:
        return render("Test alert timed out.", error=True)
    tail = "\n".join(out.splitlines()[-8:])
    if code == 0:
        return render("Test alert sent — check your phone/inbox.\n\n" + tail)
    return render("Test alert FAILED:\n\n" + tail, error=True)


@app.post("/check")
def check_now():
    subprocess.Popen(
        ["/bin/bash", os.path.join(APP_DIR, "run.sh")],
        stdout=open(LOG_PATH, "a"), stderr=subprocess.STDOUT,
    )
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("UI_PORT", "8080")))
