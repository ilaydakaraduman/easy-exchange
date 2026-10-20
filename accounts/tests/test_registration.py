import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

User = get_user_model()

VALID_PASSWORD = "ExchangeDemo1!"
DUPLICATE_EMAIL = "An account with this email already exists."
REQUIRED = "This field is required."
SHORT_PASSWORD = "This password is too short. It must contain at least 8 characters."
INVALID_EMAIL = "Enter a valid email address."


def _field_errors(html, field_name):
    match = re.search(
        rf'<ul class="[^"]*" id="id_{field_name}_error">(.*?)</ul>',
        html,
        re.S,
    )
    if match is None:
        return ""
    return match.group(1)


def _input_tag(html, field_name):
    match_start = html.find(f'name="{field_name}"')
    if match_start < 0:
        raise AssertionError(f"{field_name} was not rendered")
    start = html.rfind("<input", 0, match_start)
    end = html.find(">", match_start)
    return html[start : end + 1]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RegistrationTests(TestCase):
    def _post(self, **overrides):
        data = {
            "display_name": "Ada",
            "email": "ada@example.com",
            "password": VALID_PASSWORD,
            "confirm_password": VALID_PASSWORD,
        }
        data.update(overrides)
        return self.client.post("/register", data)

    def test_valid_registration_stores_hash_and_redirects_without_login(self):
        """Spec 01 case 1: a valid registration stores a hashed password and redirects to /login signed out."""
        response = self._post(email="  Ada@Example.COM ")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login")
        user = User.objects.get()
        self.assertEqual(user.email, "ada@example.com")
        self.assertEqual(user.display_name, "Ada")
        self.assertTrue(user.check_password(VALID_PASSWORD))
        self.assertNotEqual(user.password, VALID_PASSWORD)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_duplicate_email_differing_by_case_and_whitespace_is_rejected(self):
        """Spec 01 case 2: an email that differs only by case or whitespace is rejected."""
        User.objects.create_user(
            email="alice@example.com",
            display_name="Alice",
            password=VALID_PASSWORD,
        )

        response = self._post(
            display_name="Alice Two",
            email="  Alice@Example.COM ",
        )

        self.assertEqual(response.status_code, 200)
        email_field = _field_errors(response.content.decode(), "email")
        self.assertIn(DUPLICATE_EMAIL, email_field)
        self.assertEqual(User.objects.count(), 1)

    def test_mismatched_passwords_error_on_confirm_password(self):
        """Spec 01 case 3: passwords that differ error on the confirm password field."""
        response = self._post(confirm_password="ExchangeDemo2!")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(_field_errors(response.content.decode(), "confirm_password"))
        self.assertEqual(User.objects.count(), 0)

    def test_short_password_is_rejected_with_the_validator_message(self):
        """Spec 01 case 4: a password shorter than 8 characters is rejected on the password field."""
        response = self._post(password="abc", confirm_password="abc")

        self.assertEqual(response.status_code, 200)
        self.assertIn(SHORT_PASSWORD, _field_errors(response.content.decode(), "password"))
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_email_is_rejected(self):
        """Spec 01 case 5: an email that is not a valid address errors on the email field."""
        response = self._post(email="not-an-email")

        self.assertEqual(response.status_code, 200)
        email_field = _field_errors(response.content.decode(), "email")
        self.assertIn(INVALID_EMAIL, email_field)
        self.assertEqual(User.objects.count(), 0)

    def test_missing_display_name_is_rejected(self):
        """Spec 01 case 6: an empty display name errors on that field and creates no user."""
        response = self._post(display_name="")

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "display_name"))
        self.assertEqual(User.objects.count(), 0)

    def test_missing_email_is_rejected(self):
        """Spec 01 case 6: an empty email errors on that field and creates no user."""
        response = self._post(email="")

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "email"))
        self.assertEqual(User.objects.count(), 0)

    def test_missing_password_is_rejected(self):
        """Spec 01 case 6: an empty password errors on that field and creates no user."""
        response = self._post(password="")

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "password"))
        self.assertEqual(User.objects.count(), 0)

    def test_missing_confirm_password_is_rejected(self):
        """Spec 01 case 6: an empty confirm password errors on that field and creates no user."""
        response = self._post(confirm_password="")

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "confirm_password"))
        self.assertEqual(User.objects.count(), 0)

    def test_all_fields_missing_errors_on_every_field(self):
        """Spec 01 case 6: submitting every field empty errors on each of them."""
        response = self._post(
            display_name="",
            email="",
            password="",
            confirm_password="",
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for field_name in ("display_name", "email", "password", "confirm_password"):
            self.assertIn(REQUIRED, _field_errors(html, field_name))
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_submission_keeps_display_name_and_email_and_clears_passwords(self):
        """Spec 01 case 7: a re-rendered form keeps display name and email and clears both passwords."""
        response = self._post(confirm_password="ExchangeDemo2!")

        html = response.content.decode()
        self.assertIn('value="Ada"', _input_tag(html, "display_name"))
        self.assertIn('value="ada@example.com"', _input_tag(html, "email"))
        for field_name in ("password", "confirm_password"):
            tag = _input_tag(html, field_name)
            self.assertIn('type="password"', tag)
            self.assertNotIn("value=", tag)

    def test_post_without_csrf_token_is_rejected(self):
        """Spec 01 case 8: POST /register without a CSRF token is rejected and creates no user."""
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            "/register",
            {
                "display_name": "Ada",
                "email": "ada@example.com",
                "password": VALID_PASSWORD,
                "confirm_password": VALID_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)
