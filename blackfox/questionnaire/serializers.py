from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from questionnaire.models import Questionnaire
from questionnaire.notifications import notify_new_questionnaire
from questionnaire.tokens import new_claim_token

MAX_ANSWERS = 60
MAX_KEY_LENGTH = 64
MAX_VALUE_LENGTH = 5000
MAX_VERSION = 99

error_consent_message = 'Нужно согласие на обработку данных.'
error_answers_message = 'Некорректные ответы.'
error_version_message = 'Неизвестная версия анкеты.'


class QuestionnaireCreateSerializer(serializers.ModelSerializer):
    """Public submit. Echoes back only the id and the claim token: an
    anonymous caller never gets the (health) answers back."""

    consent = serializers.BooleanField(write_only=True)
    claim_token = serializers.CharField(read_only=True)

    class Meta:
        model = Questionnaire
        fields = ('id', 'version', 'answers', 'consent', 'claim_token')
        read_only_fields = ('id',)
        extra_kwargs = {
            'version': {'write_only': True},
            'answers': {'write_only': True},
        }

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(error_consent_message)
        return value

    def validate_version(self, value):
        if not 1 <= value <= MAX_VERSION:
            raise serializers.ValidationError(error_version_message)
        return value

    def validate_answers(self, value):
        # Only the shape is checked: the questions change in the app without
        # a backend deploy, and `version` says which edition they answer.
        if not isinstance(value, dict) or not 0 < len(value) <= MAX_ANSWERS:
            raise serializers.ValidationError(error_answers_message)
        for key, answer in value.items():
            if len(key) > MAX_KEY_LENGTH or not isinstance(answer, str):
                raise serializers.ValidationError(error_answers_message)
            if len(answer) > MAX_VALUE_LENGTH:
                raise serializers.ValidationError(error_answers_message)
        return value

    def create(self, validated_data):
        validated_data.pop('consent')
        token, token_hash, expires_at = new_claim_token()
        questionnaire = Questionnaire.objects.create(
            consent_at=timezone.now(),
            claim_token_hash=token_hash,
            claim_token_expires_at=expires_at,
            **validated_data,
        )
        transaction.on_commit(
            lambda: notify_new_questionnaire(questionnaire)
        )
        questionnaire.claim_token = token
        return questionnaire


class QuestionnaireSerializer(serializers.ModelSerializer):
    """The admin's view. PATCH may change only status and note."""

    user = serializers.SerializerMethodField()

    class Meta:
        model = Questionnaire
        fields = (
            'id', 'version', 'answers', 'created_at', 'status', 'note', 'user',
        )
        read_only_fields = ('id', 'version', 'answers', 'created_at')

    def get_user(self, obj):
        if obj.user is None:
            return None
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
        }


class MyQuestionnaireSerializer(serializers.ModelSerializer):
    """The client's own application: answers only, no status or note."""

    class Meta:
        model = Questionnaire
        fields = ('id', 'version', 'answers', 'created_at')
        read_only_fields = fields


class ClaimSerializer(serializers.Serializer):
    claim_token = serializers.CharField(max_length=200)
