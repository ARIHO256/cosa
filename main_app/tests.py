from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from .EmailBackend import EmailBackend
from .middleware import LoginCheckMiddleWare


class EmailBackendTests(TestCase):
    def setUp(self):
        self.backend = EmailBackend()
        self.password = "test-password"
        self.user = get_user_model().objects.create_user(
            email="User@example.com",
            password=self.password,
            first_name="Test",
            last_name="User",
        )

    def test_authenticate_is_case_insensitive(self):
        authenticated = self.backend.authenticate(
            request=None,
            username="user@EXAMPLE.com",
            password=self.password,
        )
        self.assertEqual(authenticated, self.user)

    def test_authenticate_rejects_wrong_password(self):
        self.assertIsNone(
            self.backend.authenticate(
                request=None,
                username=self.user.email,
                password="wrong",
            )
        )


class LoginCheckMiddlewareTests(TestCase):
    def setUp(self):
        self.middleware = LoginCheckMiddleWare(lambda request: None)
        self.factory = RequestFactory()

    def test_allows_static_requests_for_anonymous_users(self):
        request = self.factory.get(f"{settings.STATIC_URL}css/app.css")
        request.user = AnonymousUser()
        response = self.middleware.process_view(request, lambda *_: None, [], {})
        self.assertIsNone(response)
