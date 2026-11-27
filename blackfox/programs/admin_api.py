"""The admin writes the programs in the app: their days (topic and the
easy / base / hard versions) and whether the program is open."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdmin
from programs.models import ProgramDay, TrainingProgram


class DaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramDay
        fields = ('day', 'title', 'base', 'easy', 'hard')

    def validate_day(self, value):
        program = self.context['program']
        taken = ProgramDay.objects.filter(program=program, day=value)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError(
                f'День {value} уже есть в программе.')
        return value


def program_data(program):
    return {
        'slug': program.slug,
        'title': program.title,
        'is_published': program.is_published,
        'days': [{'day': d.day, 'title': d.title}
                 for d in program.days.all()],
        'clients': program.enrollments.count(),
    }


class AdminProgramsView(APIView):
    """GET /api/admin/programs/ — every program with its days."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def get(self, request):
        return Response([program_data(p) for p in TrainingProgram.objects
                         .prefetch_related('days').all()])


class AdminProgramView(APIView):
    """GET / PATCH {"is_published", "title"} /api/admin/programs/<slug>/."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def get(self, request, slug):
        return Response(program_data(
            get_object_or_404(TrainingProgram, slug=slug)))

    def patch(self, request, slug):
        program = get_object_or_404(TrainingProgram, slug=slug)
        if 'is_published' in request.data:
            program.is_published = bool(request.data['is_published'])
        if str(request.data.get('title', '')).strip():
            program.title = str(request.data['title']).strip()[:120]
        program.save()
        return Response(program_data(program))


class AdminDaysView(APIView):
    """POST /api/admin/programs/<slug>/days/ — add a day."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def post(self, request, slug):
        program = get_object_or_404(TrainingProgram, slug=slug)
        serializer = DaySerializer(data=request.data,
                                   context={'program': program})
        serializer.is_valid(raise_exception=True)
        serializer.save(program=program)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminDayView(APIView):
    """GET / PUT / DELETE /api/admin/programs/<slug>/days/<day>/."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def row(self, slug, day):
        return get_object_or_404(ProgramDay, program__slug=slug, day=day)

    def get(self, request, slug, day):
        return Response(DaySerializer(self.row(slug, day)).data)

    def put(self, request, slug, day):
        row = self.row(slug, day)
        serializer = DaySerializer(row, data=request.data, partial=True,
                                   context={'program': row.program})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, slug, day):
        self.row(slug, day).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
