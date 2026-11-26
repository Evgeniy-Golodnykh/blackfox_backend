from django.contrib import admin

from course.models import Enrollment, Lesson, LessonRead


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('day', 'title', 'is_published')
    list_editable = ('is_published',)
    ordering = ('day',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'started_on', 'bot_lessons')
    raw_id_fields = ('user',)


@admin.register(LessonRead)
class LessonReadAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'read_at')
    raw_id_fields = ('user',)
