#!/bin/bash
set -e

# cron strips the environment, so snapshot it (properly quoted) for run.sh
declare -px > /app/env.sh

# run once immediately so startup problems and the baseline alert show up
# right away instead of after the first cron tick
/bin/bash /app/run.sh >> /app/logs/main.log 2>&1 || true

exec "$@"
