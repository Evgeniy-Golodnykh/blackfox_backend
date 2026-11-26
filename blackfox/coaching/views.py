from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdmin, IsAdminOrCoach
from coaching.access import can_view, coached_ids
from coaching.models import CoachClient, CoachInvite, new_code
from coaching.serializers import PublicCoachSerializer
from coaching.services import (
    OtherCoachError, assign_coach_by_admin, join_coach,
    notify_coach_of_new_client,
)
from questionnaire.models import Questionnaire
from questionnaire.serializers import MyQuestionnaireSerializer
from training.models import Project

User = get_user_model()

bad_code_message = 'Ссылка тренера недействительна.'
not_a_client_message = 'Присоединиться к тренеру может только клиент.'
other_coach_message = ('Вы уже занимаетесь с другим тренером. Чтобы '
                       'перейти, напишите администратору.')


def invite_links(invite):
    base = settings.APP_BASE_URL.rstrip('/')
    return {
        'code': invite.code,
        'url': f'{base}/join/{invite.code}',
        'bot_url': f'https://t.me/{settings.TELEGRAM_BOT_USERNAME}'
                   f'?start=join_{invite.code}',
    }


class MyInviteView(APIView):
    """GET /api/coach/invite/ — the coach's link (made on first ask).
    POST — a new code; the previous link stops working."""

    permission_classes = (IsAuthenticated, IsAdminOrCoach)

    def get(self, request):
        invite, _ = CoachInvite.objects.get_or_create(coach=request.user)
        return Response(invite_links(invite))

    def post(self, request):
        invite, _ = CoachInvite.objects.get_or_create(coach=request.user)
        invite.code = new_code()
        invite.save(update_fields=['code'])
        return Response(invite_links(invite))


class InviteCardView(APIView):
    """GET /api/coach/invite/<code>/ — public: whose link this is, for the
    join page before anyone signs in."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request, code):
        invite = CoachInvite.objects.select_related(
            'coach__coach_profile').filter(code=code).first()
        if invite is None or not invite.coach.is_active:
            return Response({'detail': bad_code_message},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(PublicCoachSerializer(
            invite.coach, context={'request': request}).data)


class JoinView(APIView):
    """POST /api/coach/join/ {"code": …} — the signed-in client joins the
    coach whose link it is."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        if request.user.role != User.Roles.USER:
            return Response({'detail': not_a_client_message},
                            status=status.HTTP_403_FORBIDDEN)
        code = str(request.data.get('code', ''))[:16]
        invite = CoachInvite.objects.select_related('coach').filter(
            code=code, coach__is_active=True).first()
        if invite is None:
            return Response({'detail': bad_code_message},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            new = join_coach(request.user, invite.coach)
        except OtherCoachError:
            return Response({'detail': other_coach_message},
                            status=status.HTTP_409_CONFLICT)
        if new:
            notify_coach_of_new_client(invite.coach, request.user)
        coach = invite.coach
        return Response({'coach': {
            'username': coach.username,
            'first_name': coach.first_name,
            'last_name': coach.last_name,
        }, 'joined': new})


class MyClientsView(APIView):
    """GET /api/coach/clients/ — the coach's clients: with a plan
    ("active") or joined and waiting for one ("waiting"). Newest first.
    An admin may pass ?coach=<username>."""

    permission_classes = (IsAuthenticated, IsAdminOrCoach)

    def get(self, request):
        coach = request.user
        if request.user.is_admin and request.query_params.get('coach'):
            coach = get_object_or_404(User,
                                      username=request.query_params['coach'])
        ids = coached_ids(coach)
        with_project = set(Project.objects.filter(
            user_id__in=ids).values_list('user_id', flat=True))
        joined = dict(CoachClient.objects.filter(
            client_id__in=ids).values_list('client_id', 'joined_at'))
        questionnaires = dict(Questionnaire.objects.filter(
            user_id__in=ids).order_by('created_at').values_list(
            'user_id', 'id'))
        users = User.objects.filter(pk__in=ids)
        rows = [{
            'id': u.pk,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'image': request.build_absolute_uri(u.image.url)
            if u.image else None,
            'gender': u.gender,
            'fatsecret_account': bool(u.fatsecret_token),
            'status': 'active' if u.pk in with_project else 'waiting',
            'joined_at': joined[u.pk].isoformat() if u.pk in joined else None,
            'questionnaire': questionnaires.get(u.pk),
        } for u in users]
        rows.sort(key=lambda r: (r['status'] != 'waiting',
                                 r['joined_at'] or ''), reverse=False)
        return Response(rows)


class ClientQuestionnaireView(APIView):
    """GET /api/coach/clients/<username>/questionnaire/ — the client's
    latest application, for their coach (and admins)."""

    permission_classes = (IsAuthenticated, IsAdminOrCoach)

    def get(self, request, username):
        client = get_object_or_404(User, username=username)
        if not can_view(request.user, client):
            return Response(status=status.HTTP_403_FORBIDDEN)
        questionnaire = Questionnaire.objects.filter(
            user=client).order_by('-created_at').first()
        if questionnaire is None:
            return Response({'detail': 'Анкеты нет.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(MyQuestionnaireSerializer(questionnaire).data)


class CoachesView(APIView):
    """GET /api/coaches/ — public list of coaches for «Онлайн-программы»:
    profile and how many clients they lead, never e-mails."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request):
        coaches = User.objects.filter(
            role=User.Roles.COACH, is_active=True,
        ).select_related('coach_profile').annotate(
            clients_count=Count('project_coach', distinct=True)
            + Count('coach_clients', filter=Q(
                coach_clients__client__project_user__isnull=True),
                distinct=True),
        ).order_by('first_name')
        data = []
        for coach in coaches:
            row = PublicCoachSerializer(coach,
                                        context={'request': request}).data
            row['clients_count'] = coach.clients_count
            data.append(row)
        return Response(data)


def assigned_to(coach):
    """Applications the admin gave this coach, whose sender has no account
    yet (with an account they're in the coach's clients instead)."""

    from questionnaire import flow
    from questionnaire.models import ApplicationProgress

    return Questionnaire.objects.filter(
        progress__coach=coach,
        progress__stage=ApplicationProgress.Stage.ASSIGNED,
        user__isnull=True,
    ).exclude(**flow.archived_filter()).select_related('progress')


def application_row(questionnaire, with_answers=False):
    row = {
        'id': questionnaire.pk,
        'created_at': questionnaire.created_at.isoformat(),
        'assigned_at': (questionnaire.progress.assigned_at.isoformat()
                        if questionnaire.progress.assigned_at else None),
        'name': str((questionnaire.answers or {}).get('full_name') or ''),
        'contact': str((questionnaire.answers or {}).get('contact') or ''),
        'note': questionnaire.note,
    }
    if with_answers:
        row['version'] = questionnaire.version
        row['answers'] = questionnaire.answers
    return row


class MyApplicationsView(APIView):
    """GET /api/coach/applications/ — applications assigned to the coach
    by the admin, not yet signed up. Oldest first: answer them in order."""

    permission_classes = (IsAuthenticated, IsAdminOrCoach)

    def get(self, request):
        rows = [application_row(q) for q in
                assigned_to(request.user).order_by('created_at')]
        return Response(rows)


class MyApplicationView(APIView):
    """GET /api/coach/applications/<id>/ — one of them, with the answers.
    POST …/invite/ — a one-time sign-up link for the sender."""

    permission_classes = (IsAuthenticated, IsAdminOrCoach)

    def get(self, request, pk):
        questionnaire = get_object_or_404(assigned_to(request.user), pk=pk)
        return Response(application_row(questionnaire, with_answers=True))


class MyApplicationInviteView(APIView):
    permission_classes = (IsAuthenticated, IsAdminOrCoach)

    def post(self, request, pk):
        from questionnaire.views import invite_link

        questionnaire = get_object_or_404(assigned_to(request.user), pk=pk)
        return Response(invite_link(questionnaire))


class AssignCoachView(APIView):
    """POST /api/coach/assign/ {"client": …, "coach": …} — admin: put a
    client with a coach (also without a questionnaire). The coach is told
    in Telegram; a client whose plan another coach leads is refused (409).
    """

    permission_classes = (IsAuthenticated, IsAdmin)

    def post(self, request):
        client = User.objects.filter(
            username=str(request.data.get('client', '')),
            role=User.Roles.USER).first()
        coach = User.objects.filter(
            username=str(request.data.get('coach', '')),
            role=User.Roles.COACH, is_active=True).first()
        if client is None or coach is None:
            return Response({'detail': 'Нет такого клиента или тренера.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            changed = assign_coach_by_admin(client, coach)
        except OtherCoachError:
            return Response(
                {'detail': 'План клиента ведёт другой тренер — смените '
                           'тренера в проекте.'},
                status=status.HTTP_409_CONFLICT)
        return Response({'client': client.username, 'coach': coach.username,
                         'changed': changed})
