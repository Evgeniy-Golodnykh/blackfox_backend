import datetime

from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import BodyStatsDiary, FoodDiary, Project
from users.serializers import CustomUserSerializer

User = get_user_model()
current_date = datetime.date.today()


class BodyStatsDiarySerializer(serializers.ModelSerializer):
    """A serializer to read BodyStatsDiary instances."""

    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = BodyStatsDiary
        exclude = ['id']


class CreateUpdateBodyStatsDiarySerializer(serializers.ModelSerializer):
    """A serializer to create/update BodyStatsDiary instances."""

    class Meta:
        model = BodyStatsDiary
        exclude = ['id', 'user']

    def validate_date(self, input_date):
        if input_date > current_date:
            raise serializers.ValidationError(
                'The date cannot be greater than the current one'
            )
        return input_date

    def create(self, validated_data):
        user = self.context['request'].user
        date = validated_data.get('date')
        if BodyStatsDiary.objects.filter(user=user, date=date).exists():
            raise serializers.ValidationError(
                'A diary entry for the current date already exists'
            )
        validated_data['user'] = user
        return BodyStatsDiary.objects.create(**validated_data)

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return BodyStatsDiarySerializer(instance, context=context).data


class FoodDiarySerializer(serializers.ModelSerializer):
    """A serializer to read FoodDiary instances."""

    class Meta:
        model = FoodDiary
        exclude = ['id']


class ProjectSerializer(serializers.ModelSerializer):
    """A serializer to read Project instances."""

    user = CustomUserSerializer(read_only=True)
    coach = CustomUserSerializer(read_only=True)

    class Meta:
        model = Project
        exclude = ['id']


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

    def validate_user(self, value):
        if Project.objects.filter(user=value).exists():
            raise serializers.ValidationError(
                'A project with this User already exists'
            )
        return value

    def validate(self, data):
        user = data.get('user')
        coach = data.get('coach')
        if user == coach:
            raise serializers.ValidationError(
                'A user cannot be a coach at the same time'
            )
        return data

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return ProjectSerializer(instance, context=context).data
