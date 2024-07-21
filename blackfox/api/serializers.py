from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import BodyStatsDiary, FoodDiary, Project

User = get_user_model()


class BodyStatsDiarySerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyStatsDiary
        exclude = ['id']


class FoodDiarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodDiary
        exclude = ['id']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id']


class ProjectSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    coach = UserSerializer(read_only=True)
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
