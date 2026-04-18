#!/bin/bash
set -e

# Write environment variables to a file for cron to pick up
printenv | grep -E '^(EMAIL|PASSWORD|PHONE)=' > /app/.env

# Set up cron job — every 15 minutes
echo "*/15 * * * * /app/run.sh >> /app/logs/cron.log 2>&1" | crontab -

echo "CineAlert started. Polling every 15 minutes."
echo "Running initial check..."

# Run once immediately on startup
/app/run.sh

# Start cron in foreground
cron -f
