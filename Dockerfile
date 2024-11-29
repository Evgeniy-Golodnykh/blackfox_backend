FROM python:3.11-slim

# Install the Cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
  && rm -rf \
    /tmp/* \
    /usr/share/doc/* \
    /var/cache/* \
    /var/lib/apt/lists/* \
    /var/tmp/*

# Install the Python requirements package and copy the BlackFox project
WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip

RUN pip3 install -r requirements.txt --no-cache-dir

COPY blackfox/ .

CMD ["gunicorn", "blackfox.wsgi:application", "--bind", "0:8000"]
