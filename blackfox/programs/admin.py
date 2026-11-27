from django.contrib import admin

from programs.models import (
    ProgramDay, ProgramEnrollment, ProgramPrice, ProgramSchedule,
    TrainingProgram, WorkoutLog,
)


class ProgramDayInline(admin.StackedInline):
    model = ProgramDay
    extra = 1
    ordering = ('day',)


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'days_count')
    list_editable = ('is_published',)
    inlines = (ProgramDayInline,)

    @admin.display(description='тренировок')
    def days_count(self, obj):
        return obj.days.count()


@admin.register(ProgramDay)
class ProgramDayAdmin(admin.ModelAdmin):
    list_display = ('program', 'day', 'title')
    list_filter = ('program',)
    ordering = ('program', 'day')


@admin.register(ProgramEnrollment)
class ProgramEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'program', 'started_on', 'paid_until')
    list_filter = ('program',)
    list_editable = ('paid_until',)
    raw_id_fields = ('user',)


@admin.register(WorkoutLog)
class WorkoutLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'day', 'level', 'done_on', 'feel')
    list_filter = ('day__program',)
    raw_id_fields = ('user',)


@admin.register(ProgramPrice)
class ProgramPriceAdmin(admin.ModelAdmin):
    list_display = ('program', 'rubles', 'updated_at')


@admin.register(ProgramSchedule)
class ProgramScheduleAdmin(admin.ModelAdmin):
    list_display = ('program', 'mode', 'starts_on', 'gap_alerted_on')
