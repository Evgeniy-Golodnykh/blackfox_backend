from django.db.models.signals import post_save
from django.dispatch import receiver

from questionnaire.flow import mark_active_for
from training.models import Project


@receiver(post_save, sender=Project, dispatch_uid='questionnaire_active')
def application_active_when_plan_is_made(sender, instance, created,
                                         **kwargs):
    """The coach made the plan: the client's application is «На ведении»."""

    if created:
        mark_active_for(instance.user)
