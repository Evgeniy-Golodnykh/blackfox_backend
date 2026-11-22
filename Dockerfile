FROM python:3.11-slim

# Install the Cron
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron && \
    rm -rf \
    /tmp/* \
    /usr/share/doc/* \
    /var/cache/* \
    /var/lib/apt/lists/* \
    /var/tmp/*

# Copy the BlackFox project and install the Python requirements package
WORKDIR /app

COPY blackfox/ entrypoint.sh requirements.txt .

RUN python -m pip install --upgrade pip

RUN pip3 install -r requirements.txt --no-cache-dir

# Headless Chromium for the Telegram picture reports (tgbot/card_render.py).
# Debian's own package: Playwright drives it via CARD_CHROMIUM_PATH (its
# bundled browser's dependency installer doesn't know this Debian release).
RUN apt-get update && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 chromium && \
    rm -rf /var/lib/apt/lists/* /usr/share/doc/*

ENV CARD_CHROMIUM_PATH=/usr/bin/chromium

# Run entrypoint script with Cron service and BlackFox project
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
