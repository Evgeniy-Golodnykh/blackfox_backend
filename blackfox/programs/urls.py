from django.urls import path

from programs.admin_api import (
    AdminDayView, AdminDaysView, AdminProgramsView, AdminProgramView,
)
from programs.views import (
    DiaryView, MyProgramsView, ProgramDayView, ProgramView,
    StartProgramView,
)

urlpatterns = [
    path('admin/programs/', AdminProgramsView.as_view(),
         name='admin-programs'),
    path('admin/programs/<slug:slug>/', AdminProgramView.as_view(),
         name='admin-program'),
    path('admin/programs/<slug:slug>/days/', AdminDaysView.as_view(),
         name='admin-program-days'),
    path('admin/programs/<slug:slug>/days/<int:day>/',
         AdminDayView.as_view(), name='admin-program-day'),
    path('programs/', MyProgramsView.as_view(), name='programs'),
    path('programs/<slug:slug>/', ProgramView.as_view(), name='program'),
    path('programs/<slug:slug>/start/', StartProgramView.as_view(),
         name='program-start'),
    path('programs/<slug:slug>/diary/', DiaryView.as_view(),
         name='program-diary'),
    path('programs/<slug:slug>/days/<int:day>/', ProgramDayView.as_view(),
         name='program-day'),
]
