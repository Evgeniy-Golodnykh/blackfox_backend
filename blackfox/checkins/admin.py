from django.contrib import admin

from checkins.models import DailyCheckin


@admin.register(DailyCheckin)
class DailyCheckinAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'weight', 'sleep', 'wellbeing', 'stress',
                    'hunger')
    list_filter = ('date',)
    raw_id_fields = ('user',)
