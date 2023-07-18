from django.contrib.auth import get_user_model
from rest_framework import serializers

from training.models import Diet, Anthropometry
from training.services import get_data


User = get_user_model()


class DietPostSerializer(serializers.ModelSerializer):
    url = serializers.URLField()

    class Meta:
        model = Diet
        fields = ['url']

    def create(self, validated_data):
        url = validated_data['url']
        obj_in_data = get_data(url)
        obj_in_data['user'] = self.context['request'].user
        obj_in_data['url'] = url
        return Diet.objects.create(**obj_in_data)

    def update(self, instance, validated_data):
        url = validated_data['url']
        obj_in_data = get_data(url)
        obj_in_data['user'] = self.context['request'].user
        obj_in_data['url'] = url
        instance.__dict__.update(obj_in_data)
        instance.save()
        return instance


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
