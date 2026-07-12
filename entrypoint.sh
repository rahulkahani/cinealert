#!/bin/bash
set -e

# cron strips the environment, so snapshot it (properly quoted) for run.sh
declare -px > /app/env.sh

# config web UI on port 8080 — restart it if it ever crashes
(
    while true; do
        /usr/local/bin/python /app/webui.py >> /app/logs/webui.log 2>&1
        echo "$(date) - webui exited (rc=$?); restarting in 5s" >> /app/logs/webui.log
        sleep 5
    done
) &

# run once immediately so startup problems and the baseline alert show up
# right away instead of after the first cron tick
/bin/bash /app/run.sh >> /app/logs/main.log 2>&1 || true

exec "$@"
