"""Права доступа к привычкам."""
from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Доступ к объекту только у его владельца."""

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id
