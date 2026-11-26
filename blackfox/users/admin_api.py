"""The admin's view of any account: the main data (name, login, e-mail,
gender, role, blocked or not) and a coach's public profile — editable
without the self-service side effects (a changed e-mail doesn't switch the
account off here)."""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdmin
from users.mixins import UserValidationMixin
from users.models import CoachProfile
from users.serializers import CoachProfileSerializer

User = get_user_model()

own_account_message = 'Свою роль и блокировку админ здесь не меняет.'
admin_role_message = 'Роль администратора меняется только в админке Django.'
coach_has_clients_message = ('У тренера есть клиенты — сначала передайте '
                             'их другому тренеру.')
client_has_coach_message = ('У клиента есть план или тренер — тренером его '
                            'сделать нельзя, пока они есть.')


class AdminUserSerializer(UserValidationMixin, serializers.ModelSerializer):
    coach_profile = CoachProfileSerializer(required=False)
    fatsecret_account = serializers.SerializerMethodField()
    telegram = serializers.SerializerMethodField()
    coach = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'gender',
            'role', 'is_active', 'image', 'date_joined', 'last_login',
            'coach_profile', 'fatsecret_account', 'telegram', 'coach',
        )
        read_only_fields = ('id', 'image', 'date_joined', 'last_login')

    def get_fatsecret_account(self, user):
        return bool(user.fatsecret_token and user.fatsecret_secret)

    def get_telegram(self, user):
        account = getattr(user, 'telegram', None)
        return bool(account and account.can_write)

    def get_coach(self, user):
        from coaching.access import coach_of

        coach = coach_of(user)
        return coach.username if coach else None

    def validate(self, attrs):
        from coaching.access import coached_ids
        from coaching.models import CoachClient
        from training.models import Project

        user = self.instance
        viewer = self.context['request'].user
        role = attrs.get('role', user.role)
        if user.pk == viewer.pk and ('role' in attrs or 'is_active' in attrs):
            raise serializers.ValidationError(own_account_message)
        if role != user.role:
            if user.is_admin:
                raise serializers.ValidationError(admin_role_message)
            if user.is_coach and coached_ids(user):
                raise serializers.ValidationError(coach_has_clients_message)
            if role == User.Roles.COACH and (
                    Project.objects.filter(user=user).exists()
                    or CoachClient.objects.filter(client=user).exists()):
                raise serializers.ValidationError(client_has_coach_message)
        return attrs

    def update(self, instance, validated_data):
        from coaching.access import coached_ids

        profile = validated_data.pop('coach_profile', None)
        blocking_coach = (instance.is_coach and instance.is_active
                          and validated_data.get('is_active') is False)
        instance = super().update(instance, validated_data)
        if blocking_coach:
            # A blocked coach's clients are blocked too — the admin hands
            # them over and unblocks them one by one. Unblocking the coach
            # doesn't bring them back.
            self.blocked_clients = User.objects.filter(
                pk__in=coached_ids(instance), role=User.Roles.USER,
                is_active=True).update(is_active=False)
        if profile is not None and instance.is_coach:
            CoachProfile.objects.update_or_create(user=instance,
                                                  defaults=profile)
        return instance


class AdminUserView(APIView):
    """GET / PATCH /api/admin/users/<username>/ — admin only."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def get_object(self, username):
        return get_object_or_404(
            User.objects.select_related('coach_profile'), username=username)

    def get(self, request, username):
        return Response(AdminUserSerializer(
            self.get_object(username), context={'request': request}).data)

    def patch(self, request, username):
        serializer = AdminUserSerializer(
            self.get_object(username), data=request.data, partial=True,
            context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        data = dict(serializer.data)
        data['blocked_clients'] = getattr(serializer, 'blocked_clients', 0)
        return Response(data)
