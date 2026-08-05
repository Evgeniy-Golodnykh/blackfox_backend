from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from djoser.compat import get_user_email_field_name
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

error_email_message = 'A user with this e-mail already exists'
error_username_message = 'A user with that username already exists'
error_first_name_message = 'Please enter your firstname'
error_last_name_message = 'Please enter your lastname'
error_gender_message = 'Please choose correct gender'
error_role_message = 'Please choose correct role'
error_match_password_message = 'Password confirmation does not match'
error_image_message = 'Please choose an image with a size less than 5 mb'


class CustomLoginSerializer(TokenObtainPairSerializer):
    """A serializer to login User."""

    def validate(self, attrs):
        attrs['email'] = attrs.get('email').lower()  # to ignore login case
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
        )

    def get_coach(self, obj):
        project = getattr(obj, 'project_user', None)
        return project.coach.username if project else None

    def get_fatsecret_account(self, obj):
        return bool(obj.fatsecret_token)


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
    gender = serializers.CharField(
        write_only=True,
        required=True,
        max_length=6
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
            'gender',
            'role',
        )

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(error_email_message)
        return value

    def validate_username(self, value):
        value = value.strip().lower()
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(error_username_message)
        return value

    def validate_first_name(self, value):
        return value.strip().capitalize()

    def validate_last_name(self, value):
        return value.strip().capitalize()

    def validate_gender(self, value):
        value = value.strip().lower()
        if value not in ('male', 'female'):
            raise serializers.ValidationError(error_gender_message)
        return value

    def validate_role(self, value):
        value = value.strip().lower()
        if value not in ('user', 'coach'):
            raise serializers.ValidationError(error_role_message)
        return value

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
