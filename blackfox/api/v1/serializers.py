from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """A serializer to read/update User instances."""

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
        )


class SignUpSerializer(serializers.ModelSerializer):
    """A serializer to create User instances."""

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'confirm_password')

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
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """A serializer for User login."""

    @classmethod
    def get_token(cls, user):
        token = super(LoginSerializer, cls).get_token(user)
        token['username'] = user.username
        return token


class MeSerializer(serializers.ModelSerializer):
    """A serializer to read/edit own profile."""

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
        )
        read_only_fields = ('role',)
        write_only_fields = ('password',)


class ChangePasswordSerializer(serializers.ModelSerializer):
    """A serializer to change User password."""

    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('old_password', 'new_password', 'confirm_password')

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                'Password confirmation does not match.'
            )
        if attrs['new_password'] == attrs['old_password']:
            raise serializers.ValidationError(
                'New password cannot be the same as your old password.'
            )
        return attrs
