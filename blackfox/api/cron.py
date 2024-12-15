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

error_message = 'Updating data for user "{user}" failed with error "{err}"'
successful_message = 'Fatsecret data for user "{user}" successfully updated'


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
            logging.error(error_message.format(user=user.username, err=err))
            continue
        FoodDiary.objects.bulk_create(objs=objs)
        logging.info(successful_message.format(user=user.username))
        time.sleep(1)
