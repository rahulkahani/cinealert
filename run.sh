#!/bin/bash
set -e

# Load environment variables (set by entrypoint.sh for cron)
if [ -f /app/.env ]; then
    export $(cat /app/.env | xargs)
fi

cd /app
python main.py
