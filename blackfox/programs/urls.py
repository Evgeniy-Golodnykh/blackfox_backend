from django.urls import path

from programs.views import (
    DiaryView, MyProgramsView, ProgramDayView, ProgramView,
    StartProgramView,
)

urlpatterns = [
    path('programs/', MyProgramsView.as_view(), name='programs'),
    path('programs/<slug:slug>/', ProgramView.as_view(), name='program'),
    path('programs/<slug:slug>/start/', StartProgramView.as_view(),
         name='program-start'),
    path('programs/<slug:slug>/diary/', DiaryView.as_view(),
         name='program-diary'),
    path('programs/<slug:slug>/days/<int:day>/', ProgramDayView.as_view(),
         name='program-day'),
]
