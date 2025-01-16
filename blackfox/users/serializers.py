from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404
from djoser.compat import get_user_email, get_user_email_field_name
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from training.models import Project

User = get_user_model()

error_email_message = 'A user with this e-mail already exists'
error_username_message = 'A user with that username already exists'
error_first_name_message = 'Please enter your firstname'
error_last_name_message = 'Please enter your lastname'
error_role_message = 'Please choose correct role'
error_match_password_message = 'Password confirmation does not match'
error_image_message = 'Please choose an image with a size less than 5 mb'


class CustomLoginSerializer(TokenObtainPairSerializer):
    """A serializer to login User."""

    def validate(self, attrs):
        attrs['email'] = attrs.get('email').lower()  # to ignore login case
        data = super().validate(attrs)
        project = Project.objects.filter(user=self.user).first()
        data['id'] = self.user.id
        data['username'] = self.user.username
        data['email'] = self.user.email
        data['first_name'] = self.user.first_name
        data['last_name'] = self.user.last_name
        data['role'] = self.user.role
        data['coach'] = project.coach.username if project else None
        data['fatsecret_account'] = self.user.fatsecret_token is not None
        return data


class CustomUserSerializer(serializers.ModelSerializer):
    """A serializer to read User instances."""

    image = serializers.SerializerMethodField(read_only=True)
    coach = serializers.SerializerMethodField(read_only=True)
    fatsecret_account = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'image',
            'role',
            'coach',
            'fatsecret_account',
        )

    def get_image(self, obj):
        if obj.image:
            return f'{settings.BASE_URL}{settings.MEDIA_URL}{obj.image.name}'
        return None

    def get_coach(self, obj):
        user = get_object_or_404(User, email=obj.email)
        project = Project.objects.filter(user=user).first()
        return project.coach.username if project else None

    def get_fatsecret_account(self, obj):
        user = get_object_or_404(User, email=obj.email)
        return user.fatsecret_token is not None


class CustomUserCreateSerializer(serializers.ModelSerializer):
    """A serializer to create User instances."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        max_length=150,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(
        write_only=True,
        required=True,
        max_length=100
    )
    last_name = serializers.CharField(
        write_only=True,
        required=True,
        max_length=100
    )
    role = serializers.CharField(
        write_only=True,
        required=True,
        max_length=5
    )

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'password',
            'confirm_password',
            'first_name',
            'last_name',
            'role',
        )

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError(error_email_message)
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value.lower()).exists():
            raise serializers.ValidationError(error_username_message)
        return value

    def validate_role(self, value):
        if value.lower() not in ('user', 'coach'):
            raise serializers.ValidationError(error_role_message)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(error_match_password_message)
        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'].lower(),
            email=validated_data['email'].lower(),
            role=validated_data['role'].lower(),
            first_name=validated_data['first_name'].capitalize(),
            last_name=validated_data['last_name'].capitalize(),
            is_active=False,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return CustomUserSerializer(instance, context=context).data


class CustomUserUpdateSerializer(serializers.ModelSerializer):
    """A serializer to update User instances."""

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'image',
            'first_name',
            'last_name',
        )

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError(error_email_message)
        return value.lower()

    def validate_username(self, value):
        if User.objects.filter(username=value.lower()).exists():
            raise serializers.ValidationError(error_username_message)
        return value.lower()

    def validate_first_name(self, value):
        if not value or len(value) > 100:
            raise serializers.ValidationError(error_first_name_message)
        return value.capitalize()

    def validate_last_name(self, value):
        if not value or len(value) > 100:
            raise serializers.ValidationError(error_last_name_message)
        return value.capitalize()

    def validate_image(self, value):
        if not value or value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(error_image_message)
        return value

    def update(self, instance, validated_data):
        email_field = get_user_email_field_name(User)
        instance.email_changed = False
        if email_field in validated_data:
            instance_email = get_user_email(instance)
            if instance_email != validated_data[email_field]:
                instance.is_active = False
                instance.email_changed = True
                instance.save(update_fields=['is_active'])
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return CustomUserSerializer(instance, context=context).data


class CustomUserDeleteSerializer(serializers.Serializer):
    """A serializer to delete User instances."""

    class Meta:
        model = User
