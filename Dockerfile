FROM python:3.12-slim-bookworm

# chromium + matching chromedriver come from Debian, so nothing is
# downloaded at runtime and versions never drift apart.
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    chromium \
    chromium-driver \
    dos2unix \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver \
    TZ=America/Toronto \
    STATE_DIR=/app/state

# Ticket drops need a tight loop: check every 5 minutes.
RUN echo "*/5 * * * * /bin/bash /app/run.sh >> /app/logs/main.log 2>&1" > /etc/cron.d/cinealert \
    && chmod 0644 /etc/cron.d/cinealert \
    && crontab /etc/cron.d/cinealert

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
RUN mkdir -p /app/logs /app/state && touch /app/logs/main.log

RUN dos2unix /app/entrypoint.sh /app/run.sh \
    && chmod 755 /app/entrypoint.sh /app/run.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["cron", "-f"]
