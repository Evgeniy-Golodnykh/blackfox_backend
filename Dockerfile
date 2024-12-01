FROM python:3.11-slim

# Install the Cron
RUN apt-get update && apt-get install -y cron \
    && rm -rf \
    /tmp/* \
    /usr/share/doc/* \
    /var/cache/* \
    /var/lib/apt/lists/* \
    /var/tmp/*

# Install the Python requirements package and copy the BlackFox Project
WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip

RUN pip3 install -r requirements.txt --no-cache-dir

COPY blackfox/ .

# Add Entrypoint with crontab setup, start Cron service and BlackFox Project
ENTRYPOINT /bin/sh -c "touch /var/log/cron.log && \
                       printenv | grep -Ev 'BASHOPTS|BASH_VERSINFO|EUID|PPID|SHELLOPTS|UID|LANG|PWD|GPG_KEY|_=' >> /etc/environment && \
                       python manage.py crontab remove && \
                       python manage.py crontab add && \
                       service cron start && \
                       gunicorn blackfox.wsgi:application --bind 0:8000"
