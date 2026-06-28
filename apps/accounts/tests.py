from django.test import TestCase

from .models import User


class UserManagerTests(TestCase):
    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(email="Test@Example.com", password="StrongPass123!", full_name="Test User")
        self.assertEqual(user.email, "Test@example.com")
        self.assertTrue(user.check_password("StrongPass123!"))

