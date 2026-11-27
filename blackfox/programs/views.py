from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course.progress import local_today
from programs.access import (
    TRIAL_DAYS, current_day, day_state, has_paid,
)
from programs.models import (
    ProgramDay, ProgramEnrollment, TrainingProgram, WorkoutLog,
)

not_started_message = 'Программа ещё не начата.'
not_open_message = 'Эта программа скоро откроется.'
STATE_MESSAGES = {
    'later': 'Эта тренировка откроется в свой день.',
    'paywall': 'Бесплатная неделя закончилась — оформите подписку, '
               'чтобы продолжить.',
}


def log_data(log):
    if log is None:
        return None
    return {
        'level': log.level,
        'done_on': log.done_on,
        'result': log.result,
        'feel': log.feel,
        'note': log.note,
    }


def overview(enrollment, today):
    program = enrollment.program
    days = list(program.days.all())
    logs = {log.day_id: log for log in WorkoutLog.objects.filter(
        user=enrollment.user, day__program=program)}
    now = current_day(enrollment, today)
    today_row = next((d for d in days if d.day == now), None)
    upcoming = next((d for d in days if d.day > now), None)
    return {
        'program': program.slug,
        'title': program.title,
        'started_on': enrollment.started_on,
        'current_day': now,
        'trial_days': TRIAL_DAYS,
        'paid': has_paid(enrollment, today),
        'paid_until': enrollment.paid_until,
        'total_days': days[-1].day if days else 0,
        # None — a rest day (or the program is over).
        'today': (None if today_row is None else {
            'day': today_row.day,
            'title': today_row.title,
            'state': day_state(today_row.day, enrollment, today),
            'done': today_row.pk in logs,
        }),
        'next_day': upcoming.day if upcoming else None,
        'days': [{
            'day': d.day,
            'title': d.title,
            'state': day_state(d.day, enrollment, today),
            'done': d.pk in logs,
            'level': logs[d.pk].level if d.pk in logs else None,
        } for d in days],
        'done_count': len(logs),
    }


def enrollment_of(user, slug):
    return (ProgramEnrollment.objects.select_related('program')
            .filter(user=user, program__slug=slug).first())


class MyProgramsView(APIView):
    """GET /api/programs/ — the programs the user has started."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        today = local_today(request.user)
        return Response([
            overview(e, today) for e in ProgramEnrollment.objects
            .select_related('program').filter(user=request.user)
            .order_by('-started_on')])


class ProgramView(APIView):
    """GET /api/programs/<slug>/ — the user's progress in the program
    (404 if not started; `available` says whether it can be started)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, slug):
        enrollment = enrollment_of(request.user, slug)
        if enrollment is None:
            program = TrainingProgram.objects.filter(slug=slug).first()
            return Response({
                'detail': not_started_message,
                'available': bool(program and program.is_published),
            }, status=status.HTTP_404_NOT_FOUND)
        return Response(overview(enrollment, local_today(request.user)))


class StartProgramView(APIView):
    """POST /api/programs/<slug>/start/ — begin today with the free week.
    Starting again keeps the progress."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, slug):
        program = TrainingProgram.objects.filter(
            slug=slug, is_published=True).first()
        if program is None:
            return Response({'detail': not_open_message},
                            status=status.HTTP_404_NOT_FOUND)
        today = local_today(request.user)
        enrollment, _ = ProgramEnrollment.objects.get_or_create(
            user=request.user, program=program,
            defaults={'started_on': today})
        return Response(overview(enrollment, today))


class LogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkoutLog
        fields = ('level', 'result', 'feel', 'note')


def open_day(request, slug, day):
    """(enrollment, program day, today) or an error Response."""

    enrollment = enrollment_of(request.user, slug)
    if enrollment is None:
        return Response({'detail': not_started_message},
                        status=status.HTTP_404_NOT_FOUND)
    row = get_object_or_404(ProgramDay, program=enrollment.program, day=day)
    today = local_today(request.user)
    state = day_state(day, enrollment, today)
    if state != 'open':
        return Response({'detail': STATE_MESSAGES[state], 'state': state},
                        status=status.HTTP_403_FORBIDDEN)
    return enrollment, row, today


class ProgramDayView(APIView):
    """GET /api/programs/<slug>/days/<day>/ — an open workout: the three
    versions and the user's diary entry.
    PUT — write the diary entry; DELETE — remove it."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, slug, day):
        found = open_day(request, slug, day)
        if isinstance(found, Response):
            return found
        enrollment, row, _ = found
        log = WorkoutLog.objects.filter(user=request.user, day=row).first()
        return Response(self.data(row, log))

    def put(self, request, slug, day):
        found = open_day(request, slug, day)
        if isinstance(found, Response):
            return found
        enrollment, row, today = found
        log = WorkoutLog.objects.filter(user=request.user, day=row).first()
        serializer = LogSerializer(log, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(user=request.user, day=row,
                              done_on=log.done_on if log else today)
        return Response(self.data(row, log))

    def delete(self, request, slug, day):
        found = open_day(request, slug, day)
        if isinstance(found, Response):
            return found
        WorkoutLog.objects.filter(user=request.user, day=found[1]).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def data(row, log):
        days = list(row.program.days.values_list('day', flat=True))
        later = [d for d in days if d > row.day]
        earlier = [d for d in days if d < row.day]
        return {
            'day': row.day,
            'title': row.title,
            'versions': {
                'easy': row.easy or row.base,
                'base': row.base,
                'hard': row.hard or row.base,
            },
            'log': log_data(log),
            'prev_day': earlier[-1] if earlier else None,
            'next_day': later[0] if later else None,
        }


class DiaryView(APIView):
    """GET /api/programs/<slug>/diary/ — the user's entries, newest first."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, slug):
        logs = (WorkoutLog.objects.select_related('day')
                .filter(user=request.user, day__program__slug=slug))
        return Response([{
            'day': log.day.day,
            'title': log.day.title,
            **log_data(log),
        } for log in logs])


class ProgramCatalogView(APIView):
    """GET /api/programs/catalog/ — what the shop shows from the server:
    each program's price and whether it can be started."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        from programs.models import ProgramPrice

        prices = dict(ProgramPrice.objects.values_list('program__slug',
                                                       'rubles'))
        return Response([{
            'program': p.slug,
            'price': prices.get(p.slug),
            'is_published': p.is_published,
        } for p in TrainingProgram.objects.all()])
