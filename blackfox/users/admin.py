from django.contrib import admin

from users.models import CoachProfile, User

admin.site.register(CoachProfile)
admin.site.register(User)
