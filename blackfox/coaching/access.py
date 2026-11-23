"""Who may see whose data. A coach sees their own clients only — those
whose project they lead, or who joined them by link — never everyone."""

from django.contrib.auth import get_user_model

User = get_user_model()


def coached_ids(coach):
    """Ids of the users this coach works with."""

    from coaching.models import CoachClient
    from training.models import Project

    ids = set(Project.objects.filter(coach=coach).values_list('user_id',
                                                              flat=True))
    ids.update(CoachClient.objects.filter(coach=coach).values_list(
        'client_id', flat=True))
    return ids


def coach_of(user):
    """The user's coach: the project's, else the one they joined."""

    from training.models import Project

    project = Project.objects.select_related('coach').filter(
        user=user).first()
    if project is not None:
        return project.coach
    link = getattr(user, 'coach_link', None)
    return link.coach if link else None


def can_view(viewer, user):
    if viewer.is_admin or viewer.pk == user.pk:
        return True
    return viewer.is_coach and user.pk in coached_ids(viewer)


def visible(viewer, queryset, field='user'):
    """A per-user queryset cut to what the viewer may see."""

    if viewer.is_admin:
        return queryset
    if viewer.is_coach:
        ids = coached_ids(viewer) | {viewer.pk}
        return queryset.filter(**{f'{field}__in': ids})
    return queryset.filter(**{f'{field}__in': [viewer.pk]})


def target_user(request):
    """Whose data a request is about: `?user=<username>` for admins and
    coaches (refused unless they may see that user), else the viewer."""

    from django.shortcuts import get_object_or_404
    from rest_framework.exceptions import PermissionDenied

    viewer = request.user
    if not (viewer.is_admin or viewer.is_coach):
        return viewer
    username = request.query_params.get('user')
    if not username:
        return viewer
    user = get_object_or_404(User, username=username)
    if not can_view(viewer, user):
        raise PermissionDenied('Это не ваш клиент.')
    return user
