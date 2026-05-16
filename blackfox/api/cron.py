import datetime as dt
import logging
import time

from django.contrib.auth import get_user_model

from fatsecret.tools import get_fooddiary_objects
from training.models import FoodDiary

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
delete_inactive_user_message = 'Inactive {role} "{user}" has been deleted'


def fooddiary_autoupdate():
    """A function for Cron to autoupdate users Fatsecret data."""

    users = User.objects.filter(
        fatsecret_token__isnull=False,
        fatsecret_secret__isnull=False,
        project_user__isnull=False,
    )
    for user in users:
        try:
            objs = get_fooddiary_objects(user)
            FoodDiary.objects.bulk_create(objs=objs, batch_size=500)
            logging.info(fooddiary_autoupdate_successful_message.format(
                user=user.username
            ))
            time.sleep(15)
        except Exception as err:
            logging.error(fooddiary_autoupdate_error_message.format(
                user=user.username, err=err
            ))


def delete_inactive_users():
    """A function for Cron to delete inactive users."""

    inactive_users = User.objects.filter(
        is_active=False,
        date_joined__date__lt=dt.date.today() - dt.timedelta(days=2)
    )
    if not inactive_users.exists():
        return
    for user in inactive_users:
        logging.warning(delete_inactive_user_message.format(
            role=user.role, user=user.username
        ))
    inactive_users.delete()
