from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

error_email_message = 'A user with this e-mail already exists'
error_username_message = 'A user with that username already exists'
error_first_name_message = 'Please enter your firstname'
error_last_name_message = 'Please enter your lastname'
error_gender_message = 'Please choose correct gender'
error_role_message = 'Please choose correct role'
error_image_message = 'Please choose an image with a size less than 5 mb'


class UserValidationMixin:
    """Common validation logic for User serializers."""

    def validate_email(self, value):
        value = value.strip().lower()
        queryset = User.objects.filter(email=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(error_email_message)
        return value

    def validate_username(self, value):
        value = value.strip().lower()
        queryset = User.objects.filter(username=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(error_username_message)
        return value

    def validate_first_name(self, value):
        if not value or len(value) > 100:
            raise serializers.ValidationError(error_first_name_message)
        return value.strip().capitalize()

    def validate_last_name(self, value):
        if not value or len(value) > 100:
            raise serializers.ValidationError(error_last_name_message)
        return value.strip().capitalize()

    def validate_gender(self, value):
        value = value.strip().lower()
        if value not in User.Gender.values:
            raise serializers.ValidationError(error_gender_message)
        return value

    def validate_role(self, value):
        value = value.strip().lower()
        if value not in (User.Roles.USER, User.Roles.COACH):
            raise serializers.ValidationError(error_role_message)
        return value

    def validate_image(self, value):
        if not value or value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(error_image_message)
        return value
