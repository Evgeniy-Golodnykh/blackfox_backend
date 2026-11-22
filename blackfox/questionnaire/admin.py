from django.contrib import admin

from questionnaire.models import Questionnaire


@admin.register(Questionnaire)
class QuestionnaireAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'version', 'user')
    list_filter = ('status', 'version')
    readonly_fields = (
        'version', 'answers', 'consent_at', 'created_at',
        'claim_token_hash', 'claim_token_expires_at',
    )
    raw_id_fields = ('user',)
