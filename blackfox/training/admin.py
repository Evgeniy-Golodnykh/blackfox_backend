from django.contrib import admin

from training.models import BodyStatsDiary, FoodDiary, Project

admin.site.register(BodyStatsDiary)
admin.site.register(FoodDiary)
admin.site.register(Project)
