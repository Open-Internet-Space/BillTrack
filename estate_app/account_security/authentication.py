from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .service import find_user, permitted


class AccountBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 254 or len(password) > 256:
            return None
        user = find_user(username)
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        if not user:
            get_user_model()().set_password(password)

    def user_can_authenticate(self, user):
        return permitted(user)


class AccountTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not permitted(user):
            raise AuthenticationFailed('Account is awaiting approval or disabled.')
        return user, token
