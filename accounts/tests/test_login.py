import re

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings

User = get_user_model()

VALID_PASSWORD = "ExchangeDemo1!"
INVALID_LOGIN = "Invalid email or password."
REQUIRED = "This field is required."


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
class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            display_name="Alice",
            password=VALID_PASSWORD,
        )

    def _login(self, **overrides):
        data = {
            "email": "alice@example.com",
            "password": VALID_PASSWORD,
        }
        data.update(overrides)
        return self.client.post("/login", data)

    def test_valid_login_redirects_home_and_sets_session_cookie(self):
        """Spec 02 case 1: valid credentials redirect to / and set the sessionid cookie."""
        response = self._login()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertIn("sessionid", self.client.cookies)

    def test_login_accepts_email_with_different_case_and_whitespace(self):
        """Spec 02 case 2: login normalizes email the same way registration does."""
        response = self._login(email="  Alice@Example.COM ")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_shows_generic_error_and_keeps_email(self):
        """Spec 02 case 3: a wrong password re-renders the generic error with the email kept."""
        response = self._login(password="not-the-password")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(INVALID_LOGIN, html)
        self.assertIn(INVALID_LOGIN, response.context["form"].non_field_errors())
        self.assertIn('value="alice@example.com"', _input_tag(html, "email"))
        self.assertNotIn("value=", _input_tag(html, "password"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_email_matches_the_wrong_password_response(self):
        """Spec 02 case 4: an unknown email produces the same status, message, and form state."""
        response = self._login(email="nobody@example.com", password="not-the-password")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(INVALID_LOGIN, response.context["form"].non_field_errors())
        self.assertIn('value="nobody@example.com"', _input_tag(html, "email"))
        self.assertNotIn("value=", _input_tag(html, "password"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_shows_the_same_generic_error(self):
        """Spec 02 case 5: an inactive account with the right password gets the generic error."""
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self._login()

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(INVALID_LOGIN, response.context["form"].non_field_errors())
        self.assertIn('value="alice@example.com"', _input_tag(html, "email"))
        self.assertNotIn("value=", _input_tag(html, "password"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_empty_email_errors_on_the_email_field(self):
        """Spec 02 case 6: an empty email errors on that field and does not authenticate."""
        response = self._login(email="")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(html, "email"))
        self.assertNotIn(REQUIRED, _field_errors(html, "password"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_empty_password_errors_on_the_password_field(self):
        """Spec 02 case 6: an empty password errors on that field and does not authenticate."""
        response = self._login(password="")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(html, "password"))
        self.assertNotIn(REQUIRED, _field_errors(html, "email"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_both_login_fields_empty_error_on_each_field(self):
        """Spec 02 case 6: submitting both fields empty errors on each of them."""
        response = self._login(email="", password="")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(html, "email"))
        self.assertIn(REQUIRED, _field_errors(html, "password"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_safe_next_is_honoured(self):
        """Spec 02 case 7: a safe relative next redirects there; the Location header is the assertion."""
        response = self.client.post(
            "/login?next=/listings/new",
            {
                "email": "alice@example.com",
                "password": VALID_PASSWORD,
                "next": "/listings/new",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/listings/new")

    def test_absolute_next_is_ignored(self):
        """Spec 02 case 8: an absolute next URL is ignored and login lands on /."""
        response = self.client.post(
            "/login",
            {
                "email": "alice@example.com",
                "password": VALID_PASSWORD,
                "next": "https://evil.example/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_protocol_relative_next_is_ignored(self):
        """Spec 02 case 8: a protocol-relative next URL is ignored and login lands on /."""
        response = self.client.post(
            "/login",
            {
                "email": "alice@example.com",
                "password": VALID_PASSWORD,
                "next": "//evil.example/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_already_logged_in_get_login_redirects_home(self):
        """Spec 02 case 9: a logged-in user opening GET /login is redirected to /."""
        self.client.force_login(self.user)

        response = self.client.get("/login")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertNotIn('name="password"', response.content.decode())

    def test_session_key_rotates_on_login(self):
        """Spec 02 case 10: the session key after login differs from the pre-login key."""
        self.client.get("/login")
        session = self.client.session
        session["before_login"] = "1"
        session.save()
        before = self.client.session.session_key
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self._login()

        self.assertEqual(response.status_code, 302)
        after = self.client.session.session_key
        self.assertTrue(before)
        self.assertNotEqual(before, after)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_logout_flushes_the_session_and_redirects_home(self):
        """Spec 02 case 15: POST /logout redirects to / and the previous session key is gone."""
        self.client.post(
            "/login",
            {"email": "alice@example.com", "password": VALID_PASSWORD},
        )
        old_key = self.client.session.session_key

        response = self.client.post("/logout")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())

    def test_get_logout_is_method_not_allowed_and_stays_logged_in(self):
        """Spec 02 case 16: GET /logout returns 405 and leaves the user logged in."""
        self.client.force_login(self.user)

        response = self.client.get("/logout")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_logout_without_csrf_token_is_rejected(self):
        """Spec 02 case 17: POST /logout without a CSRF token returns 403 and stays logged in."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post("/logout")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)

    def test_anonymous_logout_redirects_home(self):
        """Spec 02 case 18: an anonymous POST /logout redirects to / with no error."""
        response = self.client.post("/logout")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_without_csrf_token_is_rejected(self):
        """Spec 02 case 19: POST /login without a CSRF token returns 403 and does not authenticate."""
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            "/login",
            {"email": "alice@example.com", "password": VALID_PASSWORD},
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", client.session)

    def test_anonymous_header_shows_sign_in_and_register(self):
        """Spec 02 case 20: an anonymous page shows Sign in and Register and no Logout control."""
        response = self.client.get("/")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('<a href="/login">Sign in</a>', html)
        self.assertIn('<a href="/register">Register</a>', html)
        self.assertNotIn('action="/logout"', html)
        self.assertNotIn(">Logout</button>", html)
        self.assertNotIn('href="/logout"', html)

    def test_logged_in_header_shows_display_name_and_logout_form(self):
        """Spec 02 case 20: a logged-in page shows the display name and a POST Logout form."""
        self.client.force_login(self.user)

        response = self.client.get("/")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alice", html)
        self.assertIn('<form method="post" action="/logout">', html)
        self.assertIn(">Logout</button>", html)
        self.assertNotIn('href="/login"', html)
        self.assertNotIn('href="/register"', html)
        self.assertNotIn(">Sign in</a>", html)
        self.assertNotIn(">Register</a>", html)
        self.assertNotIn('href="/logout"', html)
