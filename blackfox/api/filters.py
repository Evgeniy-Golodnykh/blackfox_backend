from django_filters import rest_framework as filters


class UniversalUserFilter(filters.FilterSet):
    """Universal filter for models with user-related field."""

    user = filters.CharFilter(method='filter_by_user')

    def filter_by_user(self, queryset, name, value):
        if value and hasattr(queryset.model, 'user'):
            return queryset.filter(user__username=value)
        return queryset
