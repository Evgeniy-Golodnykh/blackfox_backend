import datetime

from django.contrib.auth import get_user_model
from rest_framework import serializers

from fatsecret_api.tools import fatsecretdata
from training.models import BodyStatsDiary, FoodDiary, Project
from users.serializers import CustomUserSerializer

User = get_user_model()

current_date = datetime.date.today()
error_date_message = 'The date cannot be greater than the current one'
diary_entry_exists_message = (
    'A diary entry for the current user and date already exists'
)
project_exists_message = 'A project with this User already exists'
user_not_coach_message = 'A user cannot be a coach at the same time'


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
        exclude = ['user']

    def validate_date(self, input_date):
        if input_date > current_date:
            raise serializers.ValidationError(error_date_message)
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


class CreateUpdateFoodDiarySerializer(serializers.ModelSerializer):
    """A serializer to create/update FoodDiary instances."""

    class Meta:
        model = FoodDiary
        exclude = ['user']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        print(fatsecretdata(user))
        return FoodDiary.objects.create(**validated_data)


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

    def validate_user(self, user):
        if Project.objects.filter(user=user).exists():
            raise serializers.ValidationError(project_exists_message)
        return user

    def validate(self, data):
        user = data.get('user')
        coach = data.get('coach')
        if user == coach:
            raise serializers.ValidationError(user_not_coach_message)
        return data

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return ProjectSerializer(instance, context=context).data
