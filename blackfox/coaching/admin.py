from django.contrib import admin

from coaching.models import (
    CoachClient, CoachInvite, DayComment, NewClientNotice,
)


@admin.register(CoachClient)
class CoachClientAdmin(admin.ModelAdmin):
    list_display = ('client', 'coach', 'source', 'joined_at')
    list_filter = ('source',)
    raw_id_fields = ('client', 'coach')


@admin.register(CoachInvite)
class CoachInviteAdmin(admin.ModelAdmin):
    list_display = ('coach', 'code', 'created_at')
    raw_id_fields = ('coach',)


@admin.register(NewClientNotice)
class NewClientNoticeAdmin(admin.ModelAdmin):
    list_display = ('client', 'sent_at')
    raw_id_fields = ('client',)


@admin.register(DayComment)
class DayCommentAdmin(admin.ModelAdmin):
    list_display = ('client', 'date', 'coach', 'updated_at')
    raw_id_fields = ('client', 'coach')
