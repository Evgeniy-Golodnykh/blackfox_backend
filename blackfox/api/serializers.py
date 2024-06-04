from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import Diet, Anthropometry, Project

User = get_user_model()


class DietSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diet
        exclude = ['id']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id']


class MeasurementSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    measurement_date = serializers.DateField()
    steps = serializers.IntegerField(min_value=0)
    weight = serializers.FloatField(max_value=250, min_value=30)
    height = serializers.FloatField(max_value=250, min_value=30)
    waist = serializers.FloatField(max_value=150, min_value=30)
    belly = serializers.FloatField(max_value=150, min_value=30)
    hips = serializers.FloatField(max_value=150, min_value=30)
    chest = serializers.FloatField(max_value=150, min_value=30)

    class Meta:
        model = Anthropometry
        fields = ['user', 'measurement_date', 'steps', 'weight',
                  'height', 'waist', 'belly', 'hips', 'chest']


class ProjectSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    coach = UserSerializer(read_only=True)
    start_date = serializers.DateField()
    deadline = serializers.DateField()
    target_weight = serializers.FloatField(max_value=250, min_value=30)

    class Meta:
        model = Project
        fields = ['user', 'coach', 'start_date', 'deadline', 'target_weight']
