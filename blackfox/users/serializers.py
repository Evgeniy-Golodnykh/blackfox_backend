from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from training.models import Project

User = get_user_model()


class CustomLoginSerializer(TokenObtainPairSerializer):
    """A serializer to login User"""

    def validate(self, attrs):
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
    """A serializer to read/update User instances."""

    coach = serializers.SerializerMethodField(read_only=True)
    fatsecret_account = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'coach',
            'fatsecret_account',
        )

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

    class Meta:
        model = User
        fields = (
            'email',
            'username',
            'password',
            'confirm_password',
            'first_name',
            'last_name',
        )

    def validate_username(self, value):
        if value.lower() == 'me':
            raise serializers.ValidationError('Please choose another username')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                'Password confirmation does not match'
            )
        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data['first_name'].capitalize(),
            last_name=validated_data['last_name'].capitalize(),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return CustomUserSerializer(instance, context=context).data


class CustomUserDeleteSerializer(serializers.Serializer):
    """A serializer to delete User instances."""

    class Meta:
        model = User
