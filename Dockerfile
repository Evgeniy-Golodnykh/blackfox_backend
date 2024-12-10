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

# Run entrypoint script with Cron service and BlackFox project
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
