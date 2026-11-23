from django.conf import settings
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from django.contrib.auth import get_user_model

from api.permissions import IsAdmin
from questionnaire import flow
from questionnaire.models import Questionnaire
from questionnaire.serializers import (
    ClaimSerializer, MyQuestionnaireSerializer, QuestionnaireCreateSerializer,
    QuestionnaireSerializer,
)
from questionnaire.tokens import hash_claim_token, new_claim_token

invalid_claim_token_message = 'Ссылка на анкету недействительна.'
not_a_client_message = 'Привязать анкету может только клиент.'
no_questionnaire_message = 'Анкеты нет.'
already_linked_message = 'Анкета уже привязана к аккаунту.'
no_coach_message = 'Такого тренера нет.'
other_coach_message = ('У клиента уже есть план у другого тренера — '
                       'сначала смените тренера в проекте.')

User = get_user_model()


def invite_link(questionnaire):
    """A new one-time sign-up link for the application's sender; the
    previous one stops working."""

    token, token_hash, expires_at = new_claim_token()
    questionnaire.claim_token_hash = token_hash
    questionnaire.claim_token_expires_at = expires_at
    questionnaire.save(update_fields=['claim_token_hash',
                                      'claim_token_expires_at'])
    base = settings.APP_BASE_URL.rstrip('/')
    return {
        'url': f'{base}/signup?from=invite&claim={token}',
        'expires_at': expires_at.isoformat(),
    }


class QuestionnaireViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Applications from the landing page.

    POST is public (and throttled); reading and editing — admin only;
    claim/mine — the signed-in client's own application.
    """

    queryset = Questionnaire.objects.select_related(
        'user', 'progress', 'progress__coach')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    throttle_scope = 'questionnaire'
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != 'list':
            return queryset
        # Closed over 30 days ago: only on request (?archived=1).
        if self.request.query_params.get('archived'):
            return queryset.filter(**flow.archived_filter())
        return queryset.exclude(**flow.archived_filter())

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        if self.action in ('claim', 'mine'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_throttles(self):
        # Only the anonymous submit is limited, not the admin's reads.
        if self.action == 'create':
            return [ScopedRateThrottle()]
        return []

    def get_serializer_class(self):
        if self.action == 'create':
            return QuestionnaireCreateSerializer
        if self.action == 'claim':
            return ClaimSerializer
        if self.action == 'mine':
            return MyQuestionnaireSerializer
        return QuestionnaireSerializer

    @action(detail=False, methods=['post'])
    def claim(self, request):
        """Link the application sent from this device to the new account."""

        if request.user.role != request.user.Roles.USER:
            return Response(
                {'detail': not_a_client_message},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_hash = hash_claim_token(serializer.validated_data['claim_token'])
        questionnaire = Questionnaire.objects.filter(
            claim_token_hash=token_hash,
            user__isnull=True,
            claim_token_expires_at__gt=timezone.now(),
        ).first()
        # Conditional update: two claims at once can't both win.
        claimed = questionnaire is not None and Questionnaire.objects.filter(
            pk=questionnaire.pk, user__isnull=True,
        ).update(
            user=request.user,
            claim_token_hash='',
            claim_token_expires_at=None,
        )
        if not claimed:
            return Response(
                {'detail': invalid_claim_token_message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        questionnaire.refresh_from_db()
        flow.follow_assigned_coach(questionnaire)
        return Response({'id': questionnaire.pk})

    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """Admin: a one-time sign-up link for the person who sent this
        application. Signing up (or logging in) through it links the
        application to their account, as if they had done it on their own
        device right after sending it. Each call makes a new link; the
        previous one stops working."""

        questionnaire = self.get_object()
        if questionnaire.user_id is not None:
            return Response({'detail': already_linked_message},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(invite_link(questionnaire))

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Admin: {"coach": "<username>"} — the coach gets the application
        (and the linked client, if any) and a message in Telegram."""

        questionnaire = self.get_object()
        coach = User.objects.filter(
            username=str(request.data.get('coach', '')),
            role=User.Roles.COACH, is_active=True).first()
        if coach is None:
            return Response({'detail': no_coach_message},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            flow.assign_coach(questionnaire, coach)
        except flow.AssignError:
            return Response({'detail': other_coach_message},
                            status=status.HTTP_409_CONFLICT)
        questionnaire = self.get_queryset().get(pk=questionnaire.pk)
        return Response(QuestionnaireSerializer(questionnaire).data)

    @action(detail=False, methods=['get'])
    def funnel(self, request):
        """Admin: the weekly funnel (received → contacted → coach →
        active) and the median time to the first response."""

        try:
            weeks = min(max(int(request.query_params.get('weeks', 8)), 1), 26)
        except ValueError:
            weeks = 8
        return Response(flow.funnel(weeks))

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """The latest application linked to the signed-in account."""

        questionnaire = Questionnaire.objects.filter(
            user=request.user,
        ).order_by('-created_at').first()
        if questionnaire is None:
            return Response(
                {'detail': no_questionnaire_message},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(questionnaire).data)
