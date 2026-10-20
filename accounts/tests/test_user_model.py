from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class UserModelTests(TestCase):
    def test_auth_user_model_uses_email_as_username(self):
        """Task 0 / spec 01 data rules: AUTH_USER_MODEL is accounts.User and the login field is email."""
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertEqual(get_user_model().USERNAME_FIELD, "email")

    def test_create_user_normalizes_email_and_stores_a_password_hash(self):
        """Task 0 / spec 01 data rules: create_user trims and lowercases email and stores a hash."""
        user = User.objects.create_user(
            email="  Ada@Example.COM ",
            display_name="Ada",
            password="ExchangeDemo1!",
        )

        self.assertEqual(user.email, "ada@example.com")
        self.assertTrue(user.check_password("ExchangeDemo1!"))
        self.assertNotEqual(user.password, "ExchangeDemo1!")

    def test_duplicate_email_with_different_case_raises_integrity_error(self):
        """Task 0 / spec 01 data rules: email uniqueness is case-insensitive at the database."""
        User.objects.create_user(
            email="ada@example.com",
            display_name="Ada",
            password="ExchangeDemo1!",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    email="ADA@example.com",
                    display_name="Ada Two",
                    password="ExchangeDemo1!",
                )

        self.assertEqual(User.objects.count(), 1)
