from django.db.models.signals import post_save
from django.dispatch import receiver

from tgbot import onboarding
from tgbot.models import TelegramAccount
from training.models import Project


@receiver(post_save, sender=Project, dispatch_uid='tgbot_plan_ready')
def offer_reports_when_plan_is_ready(sender, instance, created, **kwargs):
    """The coach just created the plan: if the client's Telegram is linked
    and reports are still off, offer to switch them on."""

    if not created:
        return
    user = instance.user
    linked = TelegramAccount.objects.filter(user=user, can_write=True)
    if linked.exists() and not onboarding.reports_on(user):
        onboarding.send_later(user, onboarding.plan_ready)
