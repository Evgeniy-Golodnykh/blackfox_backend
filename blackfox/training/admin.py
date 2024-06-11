from django.contrib import admin

from training.models import Anthropometry, Diet, Project

admin.site.register(Anthropometry)
admin.site.register(Diet)
admin.site.register(Project)
