from rest_framework import serializers

from training.models import Diet
from training.services import get_data


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
        diet = Diet.objects.create(**obj_in_data)
        return diet

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
        fields = ['url']
