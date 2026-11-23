from rest_framework import serializers

from users.serializers import CoachProfileSerializer


class PublicCoachSerializer(serializers.Serializer):
    """What anyone may see about a coach: no e-mail, nothing private."""

    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    image = serializers.ImageField(read_only=True)
    gender = serializers.CharField(allow_null=True)
    coach_profile = serializers.SerializerMethodField()

    def get_coach_profile(self, coach):
        profile = getattr(coach, 'coach_profile', None)
        return CoachProfileSerializer(profile).data if profile else None
