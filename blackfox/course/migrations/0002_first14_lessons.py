from django.db import migrations


def load(apps, schema_editor):
    """The starting texts; edited in the admin afterwards. A lesson that
    already exists for the day is left as it is."""

    from course.lessons_first14 import LESSONS

    Lesson = apps.get_model('course', 'Lesson')
    for data in LESSONS:
        Lesson.objects.get_or_create(day=data['day'], defaults=data)


class Migration(migrations.Migration):

    dependencies = [
        ('course', '0001_course'),
    ]

    operations = [
        migrations.RunPython(load, migrations.RunPython.noop),
    ]
