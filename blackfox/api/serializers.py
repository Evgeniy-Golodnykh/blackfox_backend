from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import BodyStatsDiary, FoodDiary, Project
from users.serializers import CustomUserSerializer

User = get_user_model()


class BodyStatsDiarySerializer(serializers.ModelSerializer):
    """A serializer to read BodyStatsDiary instances."""

    class Meta:
        model = BodyStatsDiary
        exclude = ['id']


class FoodDiarySerializer(serializers.ModelSerializer):
    """A serializer to read FoodDiary instances."""

    class Meta:
        model = FoodDiary
        exclude = ['id']


class ProjectSerializer(serializers.ModelSerializer):
    """A serializer to read Project instances."""

    user = CustomUserSerializer(read_only=True)
    coach = CustomUserSerializer(read_only=True)
    start_date = serializers.DateField()
    deadline = serializers.DateField()
    target_calories = serializers.IntegerField(min_value=0, max_value=10_000)
    target_carbohydrate = serializers.FloatField(min_value=0, max_value=1_000)
    target_fat = serializers.FloatField(min_value=0, max_value=1_000)
    target_fiber = serializers.FloatField(min_value=0, max_value=1_000)
    target_protein = serializers.FloatField(min_value=0, max_value=1_000)
    target_sugar = serializers.FloatField(min_value=0, max_value=1_000)
    target_weight = serializers.FloatField(min_value=30, max_value=250)

    class Meta:
        model = Project
        exclude = ['id', 'is_closed']


class CreateUpdateProjectSerializer(serializers.ModelSerializer):
    """A serializer to create/update Project instances."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects)
    coach = serializers.PrimaryKeyRelatedField(queryset=User.objects)

    class Meta:
        model = Project
        exclude = ['id', 'is_closed']

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return ProjectSerializer(instance, context=context).data
