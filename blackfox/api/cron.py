import datetime as dt
import logging
import time

from django.contrib.auth import get_user_model
from django.db.models import Q

from fatsecret.tools import get_fooddiary_objects
from training.models import FoodDiary, Project

DATETIME_FORMAT = '%d.%m.%Y %H:%M:%S'
LOGFORMAT = '%(asctime)s [%(levelname)s] %(filename)s/%(funcName)s %(message)s'

logging.basicConfig(
    datefmt=DATETIME_FORMAT,
    format=LOGFORMAT,
    level=logging.INFO,
)

User = get_user_model()

fooddiary_autoupdate_error_message = (
    'Updating data for user "{user}" failed with error "{err}"'
)
fooddiary_autoupdate_successful_message = (
    'Fatsecret data for user "{user}" successfully updated'
)
delete_inactive_user_message = 'Inactive user "{user}" has been deleted'


def fooddiary_autoupdate():
    """A function for Cron to autoupdate users Fatsecret data."""

    users = User.objects.filter(
        Q(fatsecret_token__isnull=False) & Q(fatsecret_secret__isnull=False)
    )
    for user in users:
        if not Project.objects.filter(user=user).exists():
            continue
        try:
            objs = get_fooddiary_objects(user)
        except Exception as err:
            logging.error(fooddiary_autoupdate_error_message.format(
                user=user.username, err=err
            ))
            continue
        FoodDiary.objects.bulk_create(objs=objs)
        logging.info(fooddiary_autoupdate_successful_message.format(
            user=user.username
        ))
        time.sleep(1)


def delete_inactive_users():
    """A function for Cron to delete inactive users."""

    inactive_users = User.objects.filter(Q(is_active=False))
    for user in inactive_users:
        if (dt.date.today() - user.date_joined.date()).days > 1:
            User.objects.filter(id=user.id).delete()
            logging.info(delete_inactive_user_message.format(
                user=user.username
            ))
