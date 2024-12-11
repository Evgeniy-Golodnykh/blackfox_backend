#!/bin/sh

# Create a log file
touch /var/log/cron.log

# Copy environment variables
printenv | grep -Ev 'BASHOPTS|BASH_VERSINFO|EUID|PPID|SHELLOPTS|UID|LANG|PWD|GPG_KEY|_=' >> /etc/environment

# Add jobs to crontab
python manage.py crontab remove
python manage.py crontab add

# Start cron service
service cron start

# Start BlackFox project
exec gunicorn blackfox.wsgi:application --bind 0:8000
