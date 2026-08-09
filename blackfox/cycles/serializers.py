from django.contrib.auth import get_user_model
from rest_framework import serializers

from cycles.models import CycleSettings, PeriodEntry, PhaseOverride

User = get_user_model()

error_cycle_length_days = 'Cycle length must be greater than 0'
error_period_length_days = 'Period length must be greater than 0'
error_length_days = 'Period length cannot be greater than cycle length'


class CycleSettingsSerializer(serializers.ModelSerializer):
    """Serializer for cycle settings."""

    user = serializers.SlugRelatedField(
        queryset=User.objects,
        slug_field='username',
    )

    class Meta:
        model = CycleSettings
        fields = (
            'user',
            'cycle_length_days',
            'period_length_days',
        )

    def validate_cycle_length_days(self, value):
        if value < 1:
            raise serializers.ValidationError(error_cycle_length_days)
        return value

    def validate_period_length_days(self, value):
        if value < 1:
            raise serializers.ValidationError(error_period_length_days)
        return value

    def validate(self, attrs):
        cycle_length = attrs.get('cycle_length_days')
        period_length = attrs.get('period_length_days')
        if period_length > cycle_length:
            raise serializers.ValidationError(error_length_days)
        return attrs

    def create(self, validated_data):
        user = validated_data.pop('user')
        settings, _ = CycleSettings.objects.update_or_create(
            user=user,
            defaults=validated_data,
        )
        return settings


class PeriodEntrySerializer(serializers.ModelSerializer):
    """Serializer for period entries."""

    user = serializers.SlugRelatedField(
        queryset=User.objects,
        slug_field='username',
    )

    class Meta:
        model = PeriodEntry
        fields = '__all__'


class PhaseOverrideSerializer(serializers.ModelSerializer):
    """Serializer for phase overrides."""

    user = serializers.SlugRelatedField(
        queryset=User.objects,
        slug_field='username',
    )

    class Meta:
        model = PhaseOverride
        fields = '__all__'
