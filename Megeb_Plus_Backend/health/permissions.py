from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Only allow users to access their own health records."""

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user