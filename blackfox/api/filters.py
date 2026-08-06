from django.contrib.auth import get_user_model
from django_filters import rest_framework as filters

User = get_user_model()


class UniversalUserFilter(filters.FilterSet):
    user = filters.CharFilter(method='filter_by_user')

    def filter_by_user(self, queryset, name, value):
        if value and queryset.model is User:
            return queryset.filter(username=value)
        if value and hasattr(queryset.model, 'user'):
            return queryset.filter(user__username=value)
        return queryset


class UniversalCoachFilter(filters.FilterSet):
    coach = filters.CharFilter(method='filter_by_coach')

    def filter_by_coach(self, queryset, name, value):
        if value and queryset.model is User:
            return queryset.filter(project_user__coach__username=value)
        if value and hasattr(queryset.model, 'coach'):
            return queryset.filter(coach__username=value)
        return queryset


class UniversalUserCoachFilter(UniversalUserFilter, UniversalCoachFilter):
    role = filters.ChoiceFilter(
        choices=User.Roles.choices,
        method='filter_by_role',
    )

    def filter_by_role(self, queryset, name, value):
        if value and queryset.model is User:
            return queryset.filter(role=value)
        return queryset
