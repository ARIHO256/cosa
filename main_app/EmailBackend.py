from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate users solely by their e-mail address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.EMAIL_FIELD)

        if not username or password is None:
            return None

        try:
            user = UserModel.objects.get(email__iexact=username)
        except UserModel.DoesNotExist:
            return None

        if user.check_password(password):
            return user

        return None
