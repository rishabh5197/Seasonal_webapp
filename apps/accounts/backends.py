from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from .services import lookup_user_by_identifier


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):  # noqa: ARG002
        user_model = get_user_model()
        identifier = kwargs.get("identifier") or kwargs.get("email") or username
        if identifier is None or password is None:
            return None

        try:
            user = lookup_user_by_identifier(identifier)
        except user_model.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
