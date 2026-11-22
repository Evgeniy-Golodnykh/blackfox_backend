from django.contrib import admin

from activity.models import ActivityDay


@admin.register(ActivityDay)
class ActivityDayAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'calories_burned', 'synced_at')
    list_filter = ('date',)
    raw_id_fields = ('user',)
