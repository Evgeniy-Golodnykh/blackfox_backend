from django_filters import rest_framework as filters


class UniversalUserFilter(filters.FilterSet):
    user = filters.CharFilter(method="filter_by_user")

    def filter_by_user(self, queryset, name, value):
        if value and hasattr(queryset.model, "user"):
            return queryset.filter(user__username=value)
        return queryset


class UniversalCoachFilter(filters.FilterSet):
    coach = filters.CharFilter(method="filter_by_coach")

    def filter_by_coach(self, queryset, name, value):
        if value and hasattr(queryset.model, "coach"):
            return queryset.filter(coach__username=value)
        return queryset


class UniversalUserCoachFilter(UniversalUserFilter, UniversalCoachFilter):
    pass
