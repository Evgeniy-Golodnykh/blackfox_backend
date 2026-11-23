from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from questionnaire import flow
from questionnaire.models import ApplicationProgress, Questionnaire
from questionnaire.notifications import (
    notify_new_questionnaire, reply_to_applicant,
)
from questionnaire.tokens import new_claim_token

MAX_ANSWERS = 60
MAX_KEY_LENGTH = 64
MAX_VALUE_LENGTH = 5000
MAX_VERSION = 99

error_consent_message = 'Нужно согласие на обработку данных.'
error_answers_message = 'Некорректные ответы.'
error_version_message = 'Неизвестная версия анкеты.'
error_stage_message = 'Этот этап ставится сам или кнопкой «Назначить тренера».'
error_reason_message = 'Укажите причину.'

Stage = ApplicationProgress.Stage
MANUAL_STAGES = (Stage.NEW, Stage.CONTACTED, Stage.DECLINED, Stage.NO_ANSWER)


class StartingPlanSerializer(serializers.Serializer):
    """The plan the app showed after the submit — only echoed back to the
    sender in the bot, never stored."""

    calories = serializers.IntegerField(min_value=800, max_value=6000)
    protein = serializers.IntegerField(min_value=0, max_value=400)
    fat = serializers.IntegerField(min_value=0, max_value=400)
    carbs = serializers.IntegerField(min_value=0, max_value=1000)


class QuestionnaireCreateSerializer(serializers.ModelSerializer):
    """Public submit. Echoes back only the id and the claim token: an
    anonymous caller never gets the (health) answers back."""

    consent = serializers.BooleanField(write_only=True)
    claim_token = serializers.CharField(read_only=True)
    # Sent from the Telegram Mini App: who to answer in the bot.
    tg_init_data = serializers.CharField(write_only=True, required=False,
                                         allow_blank=True, max_length=4096)
    plan = StartingPlanSerializer(write_only=True, required=False,
                                  allow_null=True)

    class Meta:
        model = Questionnaire
        fields = ('id', 'version', 'answers', 'consent', 'claim_token',
                  'tg_init_data', 'plan')
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
        init_data = validated_data.pop('tg_init_data', '')
        plan = validated_data.pop('plan', None)
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
        telegram_id = telegram_id_of(init_data)
        if telegram_id:
            ApplicationProgress.objects.create(
                questionnaire=questionnaire, telegram_id=telegram_id)
            transaction.on_commit(
                lambda: reply_to_applicant(questionnaire, telegram_id, plan)
            )
        questionnaire.claim_token = token
        return questionnaire


def telegram_id_of(init_data):
    if not init_data:
        return None
    from tgbot.init_data import validate_init_data

    user = validate_init_data(init_data)
    return user.get('id') if user else None


def person(user):
    if user is None:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
    }


class QuestionnaireSerializer(serializers.ModelSerializer):
    """The admin's view. PATCH may change the note and the stage (new,
    contacted, declined, no answer — with a reason); a coach is assigned
    with POST …/assign/, and «На ведении» comes by itself with the plan."""

    user = serializers.SerializerMethodField()
    # Write-only here; to_representation adds the current ones.
    stage = serializers.ChoiceField(choices=MANUAL_STAGES, required=False,
                                    write_only=True)
    reason = serializers.CharField(required=False, allow_blank=True,
                                   max_length=300, write_only=True)
    coach = serializers.SerializerMethodField()
    archived = serializers.SerializerMethodField()
    stage_changed_at = serializers.SerializerMethodField()
    from_telegram = serializers.SerializerMethodField()

    class Meta:
        model = Questionnaire
        fields = (
            'id', 'version', 'answers', 'created_at', 'status', 'note', 'user',
            'stage', 'reason', 'coach', 'archived', 'stage_changed_at',
            'from_telegram',
        )
        # `status` — the old three-value field, still writable for older
        # app versions; the stage is what the app shows now.
        read_only_fields = ('id', 'version', 'answers', 'created_at')

    def to_representation(self, obj):
        data = super().to_representation(obj)
        progress = flow.getattr_progress(obj)
        data['stage'] = flow.stage_of(obj)
        data['reason'] = progress.reason if progress else ''
        return data

    def validate(self, attrs):
        stage = attrs.get('stage')
        if stage in flow.CLOSED and not attrs.get('reason', '').strip():
            raise serializers.ValidationError({'reason': error_reason_message})
        return attrs

    def update(self, instance, validated_data):
        stage = validated_data.pop('stage', None)
        reason = validated_data.pop('reason', '').strip()
        instance = super().update(instance, validated_data)
        if stage is not None and (stage != flow.stage_of(instance)
                                  or stage in flow.CLOSED):
            flow.set_stage(instance, stage, reason=reason)
        return instance

    def get_coach(self, obj):
        progress = flow.getattr_progress(obj)
        return person(progress.coach) if progress else None

    def get_archived(self, obj):
        return flow.is_archived(obj)

    def get_stage_changed_at(self, obj):
        progress = flow.getattr_progress(obj)
        changed = progress.stage_changed_at if progress else None
        return changed.isoformat() if changed else None

    def get_from_telegram(self, obj):
        progress = flow.getattr_progress(obj)
        return bool(progress and progress.telegram_id)

    def get_user(self, obj):
        return person(obj.user)


class MyQuestionnaireSerializer(serializers.ModelSerializer):
    """The client's own application: answers only, no status or note."""

    class Meta:
        model = Questionnaire
        fields = ('id', 'version', 'answers', 'created_at')
        read_only_fields = fields


class ClaimSerializer(serializers.Serializer):
    claim_token = serializers.CharField(max_length=200)
