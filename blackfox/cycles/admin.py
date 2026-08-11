from django.contrib import admin

from cycles.models import CycleSettings, PeriodEntry, PhaseOverride

admin.site.register(CycleSettings)
admin.site.register(PeriodEntry)
admin.site.register(PhaseOverride)
