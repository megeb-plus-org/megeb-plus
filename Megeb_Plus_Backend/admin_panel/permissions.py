from rest_framework import permissions


class IsAdminRole(permissions.BasePermission):
    """Only allow users with role='admin' to access admin panel endpoints."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )