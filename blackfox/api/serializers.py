import datetime as dt

from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import BodyStatsDiary, FoodDiary, Project
from users.serializers import CustomUserSerializer

User = get_user_model()

current_date = dt.date.today()
error_coach_message = 'The coach does not have the appropriate role'
error_big_date_message = 'The date cannot be greater than the current one'
error_small_date_message = 'The date cannot be less than 15 days ago'
error_user_message = 'The user is admin or coach, please choose another one'
diary_entry_exists_message = (
    'A diary entry for the current user and date already exists'
)
project_exists_message = 'A project with this User already exists'


class BodyStatsDiarySerializer(serializers.ModelSerializer):
    """A serializer to read BodyStatsDiary instances."""

    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = BodyStatsDiary
        fields = '__all__'


class CreateUpdateBodyStatsDiarySerializer(serializers.ModelSerializer):
    """A serializer to create/update BodyStatsDiary instances."""

    class Meta:
        model = BodyStatsDiary
        exclude = ('user',)

    def validate_date(self, input_date):
        if input_date > current_date:
            raise serializers.ValidationError(error_big_date_message)
        return input_date

    def create(self, validated_data):
        user = self.context['request'].user
        date = validated_data.get('date')
        if BodyStatsDiary.objects.filter(user=user, date=date).exists():
            raise serializers.ValidationError(diary_entry_exists_message)
        validated_data['user'] = user
        return BodyStatsDiary.objects.create(**validated_data)

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return BodyStatsDiarySerializer(instance, context=context).data


class FoodDiarySerializer(serializers.ModelSerializer):
    """A serializer to read FoodDiary instances."""

    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = FoodDiary
        fields = '__all__'


class ProjectSerializer(serializers.ModelSerializer):
    """A serializer to read Project instances."""

    user = CustomUserSerializer(read_only=True)
    coach = CustomUserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = '__all__'


class CreateUpdateProjectSerializer(ProjectSerializer):
    """A serializer to create/update Project instances."""

    user = serializers.SlugRelatedField(
        queryset=User.objects,
        slug_field='username',
    )
    coach = serializers.SlugRelatedField(
        queryset=User.objects,
        slug_field='username',
    )

    def validate_start_date(self, input_date):
        if input_date > current_date:
            raise serializers.ValidationError(error_big_date_message)
        if input_date < current_date - dt.timedelta(15):
            raise serializers.ValidationError(error_small_date_message)
        return input_date

    def validate_coach(self, user):
        if not user.is_coach:
            raise serializers.ValidationError(error_coach_message)
        return user

    def validate_user(self, user):
        if user.is_admin or user.is_coach:
            raise serializers.ValidationError(error_user_message)
        if Project.objects.filter(user=user).exists():
            raise serializers.ValidationError(project_exists_message)
        return user

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return ProjectSerializer(instance, context=context).data
