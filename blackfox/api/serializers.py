from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import FitnessDiary, Project

User = get_user_model()


class FitnessDiarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FitnessDiary
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
    target_weight = serializers.FloatField(max_value=250, min_value=30)

    class Meta:
        model = Project
        fields = ['user', 'coach', 'start_date', 'deadline', 'target_weight']
