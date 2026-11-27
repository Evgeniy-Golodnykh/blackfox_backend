from django.db import migrations


def load(apps, schema_editor):
    """The four shop programs run as calendar streams; the admin sets the
    date of day 1 in the app before opening them."""

    TrainingProgram = apps.get_model('programs', 'TrainingProgram')
    ProgramSchedule = apps.get_model('programs', 'ProgramSchedule')
    for program in TrainingProgram.objects.filter(
            slug__in=['hyrox', 'crossfit', 'running', 'functional']):
        ProgramSchedule.objects.get_or_create(
            program=program, defaults={'mode': 'calendar'})


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0004_program_schedule'),
    ]

    operations = [
        migrations.RunPython(load, migrations.RunPython.noop),
    ]
