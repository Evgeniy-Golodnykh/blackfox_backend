from django.contrib.auth.password_validation import validate_password
from djoser.compat import get_user_email_field_name
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.mixins import UserValidationMixin
from users.models import CoachProfile, User

error_match_password_message = 'Password confirmation does not match'


class CoachProfileSerializer(serializers.ModelSerializer):
    """A serializer to read CoachProfile instances."""

    class Meta:
        model = CoachProfile
        exclude = ('user',)


class CustomLoginSerializer(TokenObtainPairSerializer):
    """A serializer to login User."""

    def validate(self, attrs):
        attrs['email'] = attrs.get('email').strip().lower()
        data = super().validate(attrs)
        data.update(
            CustomUserSerializer(self.user, context=self.context,).data
        )
        return data


class CustomUserSerializer(serializers.ModelSerializer):
    """A serializer to read User instances."""

    image = serializers.ImageField(read_only=True)
    coach = serializers.SerializerMethodField(read_only=True)
    fatsecret_account = serializers.SerializerMethodField(read_only=True)
    coach_profile = CoachProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'image',
            'gender',
            'role',
            'coach',
            'fatsecret_account',
            'coach_profile',
        )

    def get_coach(self, obj):
        project = getattr(obj, 'project_user', None)
        return project.coach.username if project else None

    def get_fatsecret_account(self, obj):
        return bool(obj.fatsecret_token)


class CustomUserCreateSerializer(
    UserValidationMixin, serializers.ModelSerializer
):
    """A serializer to create User instances."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        max_length=150,
        validators=[validate_password],
    )
    confirm_password = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(write_only=True, required=True)
    last_name = serializers.CharField(write_only=True, required=True)
    gender = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'password',
            'confirm_password',
            'first_name',
            'last_name',
            'gender',
            'role',
        )

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(error_match_password_message)
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User(**validated_data, is_active=False)
        user.set_password(password)
        user.save()
        return user

    def to_representation(self, instance):
        return CustomUserSerializer(instance, context=self.context).data


class CustomUserUpdateSerializer(
    UserValidationMixin, serializers.ModelSerializer
):
    """A serializer to update User instances."""

    coach_profile = CoachProfileSerializer(required=False)

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'gender',
            'image',
            'coach_profile',
        )

    def update(self, instance, validated_data):
        email_field = get_user_email_field_name(User)
        instance.email_changed = False
        coach_profile_data = validated_data.pop('coach_profile', None)
        if email_field in validated_data:
            instance.is_active = False
            instance.email_changed = True
        if coach_profile_data and instance.is_coach:
            coach_profile, _ = CoachProfile.objects.update_or_create(
                user=instance,
                defaults=coach_profile_data,
            )
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return CustomUserSerializer(instance, context=self.context).data


class CustomUserDeleteSerializer(serializers.Serializer):
    """A serializer to delete User instances."""

    class Meta:
        model = User
