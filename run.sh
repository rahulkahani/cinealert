#!/bin/bash
# shellcheck disable=SC1091
[ -f /app/env.sh ] && source /app/env.sh

# never let two checks overlap (Chrome discovery can be slow)
exec 9>/tmp/cinealert.lock
if ! flock -n 9; then
    echo "$(date) - previous run still in progress; skipping"
    exit 0
fi

/usr/local/bin/python /app/main.py "$@"
