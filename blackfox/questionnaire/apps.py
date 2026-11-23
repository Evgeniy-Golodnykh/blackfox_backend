from django.apps import AppConfig


class QuestionnaireConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'questionnaire'
    verbose_name = 'Анкеты'

    def ready(self):
        from questionnaire import signals  # noqa: F401 — registers receivers
