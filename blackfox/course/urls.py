from django.urls import path

from course.views import CourseView, LessonView, StartCourseView

urlpatterns = [
    path('course/', CourseView.as_view(), name='course'),
    path('course/start/', StartCourseView.as_view(), name='course-start'),
    path('course/lessons/<int:day>/', LessonView.as_view(),
         name='course-lesson'),
]
