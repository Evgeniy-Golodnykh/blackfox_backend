from django.db import migrations

PROGRAMS = [
    ('hyrox', 'Hyrox'),
    ('crossfit', 'CrossFit'),
    ('running', 'Running'),
    ('functional', 'Functional Fitness'),
]


def load(apps, schema_editor):
    """The four programs of the shop, closed until their days are written
    in the admin. One that already exists is left as it is."""

    TrainingProgram = apps.get_model('programs', 'TrainingProgram')
    for slug, title in PROGRAMS:
        TrainingProgram.objects.get_or_create(
            slug=slug, defaults={'title': title, 'is_published': False})


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0001_training_programs'),
    ]

    operations = [
        migrations.RunPython(load, migrations.RunPython.noop),
    ]
