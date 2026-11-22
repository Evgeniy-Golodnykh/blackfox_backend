from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from api.permissions import IsAdmin
from questionnaire.models import Questionnaire
from questionnaire.serializers import (
    ClaimSerializer, MyQuestionnaireSerializer, QuestionnaireCreateSerializer,
    QuestionnaireSerializer,
)
from questionnaire.tokens import hash_claim_token

invalid_claim_token_message = 'Ссылка на анкету недействительна.'
not_a_client_message = 'Привязать анкету может только клиент.'
no_questionnaire_message = 'Анкеты нет.'


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

    queryset = Questionnaire.objects.select_related('user')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    throttle_scope = 'questionnaire'
    pagination_class = None

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
        return Response({'id': questionnaire.pk})

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
