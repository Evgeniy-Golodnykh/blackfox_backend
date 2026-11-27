"""The admin writes the programs in the app: their days (topic and the
easy / base / hard versions) and whether the program is open."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdmin
from programs.models import ProgramDay, ProgramPrice, TrainingProgram


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


def price_of(program):
    row = ProgramPrice.objects.filter(program=program).first()
    return row.rubles if row else None


def program_data(program):
    return {
        'slug': program.slug,
        'title': program.title,
        'is_published': program.is_published,
        'price': price_of(program),
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
        if 'price' in request.data:
            price = request.data['price']
            if price in (None, ''):
                price = None
            else:
                try:
                    price = int(price)
                except (TypeError, ValueError):
                    price = -1
                if not 0 < price <= 1_000_000:
                    return Response(
                        {'price': ['Цена — целое число рублей от 1.']},
                        status=status.HTTP_400_BAD_REQUEST)
            ProgramPrice.objects.update_or_create(
                program=program, defaults={'rubles': price})
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


class ImportDaySerializer(DaySerializer):
    def validate_day(self, value):
        return value  # duplicates are checked across the whole upload


class AdminImportView(APIView):
    """POST /api/admin/programs/<slug>/import/ {"days": [...], "replace"}
    — the whole program at once (parsed in the app, shown as a preview).
    Days that exist are rewritten, new ones added; with "replace": true
    the days not in the upload are deleted. All or nothing."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def post(self, request, slug):
        program = get_object_or_404(TrainingProgram, slug=slug)
        rows = request.data.get('days')
        if not isinstance(rows, list) or not rows:
            return Response({'days': ['Нет ни одного дня.']},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = ImportDaySerializer(data=rows, many=True,
                                         context={'program': program})
        serializer.is_valid(raise_exception=True)
        days = [row['day'] for row in serializer.validated_data]
        repeated = sorted({d for d in days if days.count(d) > 1})
        if repeated:
            listed = ', '.join(map(str, repeated))
            return Response({'days': [f'Повторяются дни: {listed}.']},
                            status=status.HTTP_400_BAD_REQUEST)
        created = updated = 0
        with transaction.atomic():
            deleted = 0
            if request.data.get('replace') is True:
                deleted, _ = (ProgramDay.objects.filter(program=program)
                              .exclude(day__in=days).delete())
            for row in serializer.validated_data:
                values = {k: row.get(k, '') for k in
                          ('title', 'base', 'easy', 'hard')}
                _, new = ProgramDay.objects.update_or_create(
                    program=program, day=row['day'], defaults=values)
                created += new
                updated += not new
        data = program_data(program)
        data.update({'created': created, 'updated': updated,
                     'deleted': deleted})
        return Response(data)
