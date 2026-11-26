from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Enrollment, Lesson, LessonRead
from course.progress import (
    current_day, enrollment_for, is_open, local_today, overview,
    read_days_of,
)

only_clients_message = 'Курс — для клиентов.'
locked_message = 'Этот урок откроется позже.'


class CourseView(APIView):
    """GET /api/course/ — the client's course: lessons, which are open,
    which are read. A new client is enrolled on the first visit.
    PATCH {"bot_lessons": false} — no lessons in the bot."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(overview(request.user, enrollment_for(request.user)))

    def patch(self, request):
        enrollment = enrollment_for(request.user)
        if enrollment is None:
            return Response({'detail': 'Курс ещё не начат.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if 'bot_lessons' in request.data:
            enrollment.bot_lessons = bool(request.data['bot_lessons'])
            enrollment.save(update_fields=['bot_lessons'])
        return Response(overview(request.user, enrollment))


class StartCourseView(APIView):
    """POST /api/course/start/ — begin the course today."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        if request.user.role != request.user.Roles.USER:
            return Response({'detail': only_clients_message},
                            status=status.HTTP_403_FORBIDDEN)
        enrollment = enrollment_for(request.user, start=True)
        return Response(overview(request.user, enrollment))


class LessonView(APIView):
    """GET /api/course/lessons/<day>/ — an open lesson (its calendar day
    has come, or the one before it is read); reading it marks it read and
    opens the next."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, day):
        enrollment = Enrollment.objects.filter(user=request.user).first()
        lesson = Lesson.objects.filter(day=day, is_published=True).first()
        if lesson is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if enrollment is None or not is_open(
                day, current_day(enrollment, local_today(request.user)),
                read_days_of(request.user)):
            return Response({'detail': locked_message},
                            status=status.HTTP_403_FORBIDDEN)
        LessonRead.objects.get_or_create(user=request.user, lesson=lesson)
        total = Lesson.objects.filter(is_published=True).count()
        following = Lesson.objects.filter(
            is_published=True, day__gt=lesson.day).order_by('day').first()
        return Response({
            'day': lesson.day,
            'total': total,
            'title': lesson.title,
            'summary': lesson.summary,
            'body': lesson.body,
            'action': lesson.action,
            'sources': [line.strip() for line in lesson.sources.splitlines()
                        if line.strip()],
            # Open now that this one is read.
            'next_day': following.day if following else None,
        })
