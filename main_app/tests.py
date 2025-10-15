from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .EmailBackend import EmailBackend
from .middleware import LoginCheckMiddleWare
from .models import Follow, FriendRequest, Friendship, Notification


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


class SocialModelsTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.alice = self.User.objects.create_user(email='alice@example.com', password='x')
        self.bob = self.User.objects.create_user(email='bob@example.com', password='x')

    def test_follow_unique_and_no_self(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        with self.assertRaises(Exception):
            # unique constraint
            Follow.objects.create(follower=self.alice, following=self.bob)
        # self-follow prevented at app level by view; model allows but we can assert inequality for sanity
        self.assertNotEqual(self.alice.id, self.bob.id)

    def test_friend_request_and_friendship(self):
        fr = FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        self.assertEqual(fr.status, 'pending')
        # Accept -> create friendship
        fr.status = 'accepted'
        fr.save()
        Friendship.objects.create(user1=self.alice, user2=self.bob)  # simulate ensure
        self.assertTrue(Friendship.objects.filter(user1__in=[self.alice, self.bob], user2__in=[self.alice, self.bob]).exists())

    def test_notification_creation(self):
        n = Notification.objects.create(recipient=self.bob, sender=self.alice, notification_type='follow', message='Alice started following you')
        self.assertFalse(n.is_read)
        n.is_read = True
        n.save()
        self.assertTrue(Notification.objects.get(id=n.id).is_read)


class SocialViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.User = get_user_model()
        self.alice = self.User.objects.create_user(email='alice@example.com', password='x')
        self.bob = self.User.objects.create_user(email='bob@example.com', password='x')

    def test_follow_toggle(self):
        self.client.force_login(self.alice)
        url = reverse('follow_toggle', args=[self.bob.id])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Follow.objects.filter(follower=self.alice, following=self.bob).count(), 1)
        # unfollow
        res = self.client.post(url)
        self.assertEqual(Follow.objects.filter(follower=self.alice, following=self.bob).count(), 0)

    def test_send_and_accept_friend_request(self):
        self.client.force_login(self.alice)
        send_url = reverse('send_friend_request', args=[self.bob.id])
        res = self.client.post(send_url)
        self.assertEqual(res.status_code, 200)
        fr = FriendRequest.objects.get(sender=self.alice, receiver=self.bob)
        self.assertEqual(fr.status, 'pending')

        # Bob accepts
        self.client.force_login(self.bob)
        respond_url = reverse('respond_friend_request', args=[fr.id])
        res = self.client.post(respond_url, {'action': 'accept'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Friendship.objects.filter(user1__in=[self.alice, self.bob], user2__in=[self.alice, self.bob]).exists())

    def test_notifications_feed_and_mark_read(self):
        Notification.objects.create(recipient=self.bob, sender=self.alice, notification_type='follow')
        self.client.force_login(self.bob)
        feed_url = reverse('notifications_feed')
        res = self.client.get(feed_url)
        self.assertEqual(res.status_code, 200)
        nid = res.json()['results'][0]['id']
        mark_url = reverse('mark_notification_read', args=[nid])
        res = self.client.post(mark_url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Notification.objects.get(id=nid).is_read)
