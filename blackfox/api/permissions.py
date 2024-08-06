from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """Object-level permission to only allow admins to edit."""

    message = 'Only admin can perform this.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsCoach(permissions.BasePermission):
    """Object-level permission to only allow coach to edit."""

    message = 'Only coach can perform this.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_coach
