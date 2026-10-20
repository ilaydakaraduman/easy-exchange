import re
from html import unescape

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import MVP_CATEGORIES

User = get_user_model()

RANGE_MESSAGE = "Ensure this value is between 1 and 10."
WHOLE_NUMBER = "Enter a whole number."
REQUIRED = "This field is required."
GOOD_CHOICE = "Select a valid choice. Good is not one of the available choices."
MIN_ONLY = "Ensure this value is greater than or equal to"
MAX_ONLY = "Ensure this value is less than or equal to"


def _post_form(html):
    match = re.search(
        r'<form method="post" action="/listings/new"(.*?)</form>',
        html,
        re.S,
    )
    if match is None:
        raise AssertionError("listing form was not rendered")
    return match.group(1)


def _field_names(form_html):
    return [
        name
        for name in re.findall(r'name="([^"]+)"', form_html)
        if name != "csrfmiddlewaretoken"
    ]


def _control(form_html, name):
    for match in re.finditer(r"<(input|textarea|select)\b([^>]*)>", form_html):
        opening = match.group(0)
        if f'name="{name}"' not in opening:
            continue
        kind = match.group(1)
        body = ""
        if kind in ("select", "textarea"):
            close = form_html.index(f"</{kind}>", match.end())
            body = form_html[match.end() : close]
        return kind, opening, body
    raise AssertionError(f"{name} was not rendered")


def _field_errors(html, field_name):
    match = re.search(
        rf'<ul class="[^"]*" id="id_{field_name}_error">(.*?)</ul>',
        html,
        re.S,
    )
    if match is None:
        return ""
    return match.group(1)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CreateListingTests(TestCase):
    def setUp(self):
        for spec in MVP_CATEGORIES:
            Category.objects.create(
                slug=spec["slug"],
                name=spec["name"],
                metadata_schema=spec["metadata_schema"],
            )
        self.user = User.objects.create_user(
            email="ada@example.com",
            display_name="Ada",
            password="ExchangeDemo1!",
        )

    def _login(self):
        self.client.force_login(self.user)

    def _funko(self, **overrides):
        data = {
            "category": "funko",
            "title": "  Demo Funko  ",
            "description": "  A funko listing.  ",
            "box_condition": "7",
            "original_box_included": "on",
            "serial_number": "FP-0001",
        }
        data.update(overrides)
        return data

    def test_anonymous_get_redirects_to_login_with_next(self):
        """Spec 03 case 13: anonymous GET /listings/new redirects to /login?next=/listings/new."""
        response = self.client.get("/listings/new")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login?next=/listings/new")
        self.assertNotIn("Continue", response.content.decode())
        self.assertEqual(Item.objects.count(), 0)

    def test_anonymous_post_redirects_to_login_without_next(self):
        """Spec 03 case 13: anonymous POST /listings/new redirects to /login and saves nothing."""
        response = self.client.post("/listings/new", self._funko())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login")
        self.assertNotIn("next=", response["Location"])
        self.assertEqual(Item.objects.count(), 0)

    def test_step_one_renders_the_category_chooser_only(self):
        """Spec 03 case 14: GET /listings/new shows the three categories and no listing fields."""
        self._login()

        response = self.client.get("/listings/new")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        options = [
            (value, unescape(text))
            for value, text in re.findall(
                r'<option value="([^"]*)"[^>]*>(.*?)</option>',
                html,
            )
        ]
        self.assertEqual(
            options,
            [
                ("funko", "Funko Pop & Figures"),
                ("lego", "Lego Sets & Minifigures"),
                ("tcg", "Trading Card Games"),
            ],
        )
        self.assertIn(">Continue</button>", html)
        for name in (
            "title",
            "description",
            "box_condition",
            "original_box_included",
            "serial_number",
            "sealed_misb",
            "missing_parts",
            "year",
            "grading",
            "card_condition",
        ):
            self.assertNotIn(f'name="{name}"', html)

    def test_funko_step_two_renders_only_funko_inputs(self):
        """Spec 03 case 15: the funko form has the funko inputs in schema order."""
        self._login()

        response = self.client.get("/listings/new?category=funko")

        html = response.content.decode()
        form = _post_form(html)
        self.assertEqual(
            _field_names(form),
            [
                "category",
                "title",
                "description",
                "photo",
                "box_condition",
                "original_box_included",
                "serial_number",
            ],
        )
        self.assertIn('<option value="funko" selected>', html)
        self.assertIn("Funko Pop & Figures", unescape(html))
        kind, opening, _body = _control(form, "category")
        self.assertEqual(kind, "input")
        self.assertIn('type="hidden"', opening)
        self.assertIn('value="funko"', opening)
        kind, opening, _body = _control(form, "title")
        self.assertEqual(kind, "input")
        self.assertIn('type="text"', opening)
        kind, _opening, _body = _control(form, "description")
        self.assertEqual(kind, "textarea")
        kind, opening, _body = _control(form, "box_condition")
        self.assertEqual(kind, "input")
        self.assertIn('type="number"', opening)
        self.assertIn('min="1"', opening)
        self.assertIn('max="10"', opening)
        kind, opening, _body = _control(form, "original_box_included")
        self.assertEqual(kind, "input")
        self.assertIn('type="checkbox"', opening)
        kind, opening, _body = _control(form, "serial_number")
        self.assertEqual(kind, "input")
        self.assertIn('type="text"', opening)
        for name in ("sealed_misb", "missing_parts", "year", "grading", "card_condition"):
            self.assertNotIn(f'name="{name}"', html)

    def test_lego_step_two_renders_only_lego_inputs(self):
        """Spec 03 case 15: the lego form has checkboxes and a year input with no min or max."""
        self._login()

        response = self.client.get("/listings/new?category=lego")

        html = response.content.decode()
        form = _post_form(html)
        self.assertEqual(
            _field_names(form),
            [
                "category",
                "title",
                "description",
                "photo",
                "sealed_misb",
                "missing_parts",
                "year",
            ],
        )
        self.assertIn('<option value="lego" selected>', html)
        for name in ("sealed_misb", "missing_parts"):
            kind, opening, _body = _control(form, name)
            self.assertEqual(kind, "input")
            self.assertIn('type="checkbox"', opening)
        kind, opening, _body = _control(form, "year")
        self.assertEqual(kind, "input")
        self.assertIn('type="number"', opening)
        self.assertNotIn("min=", opening)
        self.assertNotIn("max=", opening)
        for name in (
            "box_condition",
            "original_box_included",
            "serial_number",
            "grading",
            "card_condition",
        ):
            self.assertNotIn(f'name="{name}"', html)

    def test_tcg_step_two_renders_optional_grading_and_condition_choices(self):
        """Spec 03 case 15: the tcg form has optional grading and a blank-plus-choices select."""
        self._login()

        response = self.client.get("/listings/new?category=tcg")

        html = response.content.decode()
        form = _post_form(html)
        self.assertEqual(
            _field_names(form),
            [
                "category",
                "title",
                "description",
                "photo",
                "grading",
                "card_condition",
                "game",
                "set_name",
            ],
        )
        self.assertIn('<option value="tcg" selected>', html)
        kind, opening, _body = _control(form, "grading")
        self.assertEqual(kind, "input")
        self.assertIn('type="text"', opening)
        self.assertNotIn("required", opening)
        kind, opening, body = _control(form, "card_condition")
        self.assertEqual(kind, "select")
        options = re.findall(r"<option\b([^>]*)>([^<]*)</option>", body)
        values = []
        for attrs, text in options:
            value = re.search(r'value="([^"]*)"', attrs)
            values.append((value.group(1) if value else "", text.strip()))
        self.assertEqual(
            values,
            [("", ""), ("Mint", "Mint"), ("Near Mint", "Near Mint"), ("Played", "Played")],
        )
        for name in (
            "box_condition",
            "original_box_included",
            "serial_number",
            "sealed_misb",
            "missing_parts",
            "year",
        ):
            self.assertNotIn(f'name="{name}"', html)

    def test_unknown_category_get_returns_404(self):
        """Spec 03 case 16: GET /listings/new?category=sports returns 404."""
        self._login()

        response = self.client.get("/listings/new?category=sports")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Item.objects.count(), 0)

    def test_unknown_category_post_returns_404(self):
        """Spec 03 case 16: POST /listings/new with category=sports returns 404 and saves nothing."""
        self._login()

        response = self.client.post("/listings/new", self._funko(category="sports"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Item.objects.count(), 0)

    def test_valid_funko_create_stores_metadata_and_redirects(self):
        """Spec 03 case 17: a valid funko post creates an AVAILABLE item and redirects to its detail path."""
        self._login()

        response = self.client.post("/listings/new", self._funko())

        item = Item.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{item.pk}")
        self.assertEqual(item.owner, self.user)
        self.assertEqual(item.category.slug, "funko")
        self.assertEqual(item.status, Item.Status.AVAILABLE)
        self.assertEqual(item.title, "Demo Funko")
        self.assertEqual(item.description, "A funko listing.")
        self.assertEqual(
            item.metadata,
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

    def test_unchecked_checkbox_is_stored_as_false(self):
        """Spec 03 case 17: an unchecked required checkbox is stored as false."""
        self._login()
        data = self._funko()
        data.pop("original_box_included")

        response = self.client.post("/listings/new", data)

        item = Item.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{item.pk}")
        self.assertEqual(item.metadata["original_box_included"], False)

    def test_valid_lego_create_stores_metadata(self):
        """Spec 03 case 17: a valid lego post stores the lego metadata and redirects."""
        self._login()

        response = self.client.post(
            "/listings/new",
            {
                "category": "lego",
                "title": "Demo Lego",
                "description": "A lego listing.",
                "sealed_misb": "on",
                "year": "2019",
            },
        )

        item = Item.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{item.pk}")
        self.assertEqual(item.category.slug, "lego")
        self.assertEqual(item.status, Item.Status.AVAILABLE)
        self.assertEqual(
            item.metadata,
            {"sealed_misb": True, "missing_parts": False, "year": 2019},
        )

    def test_blank_grading_is_omitted(self):
        """Spec 03 case 17: a blank optional grading value is omitted from metadata."""
        self._login()

        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Demo Card",
                "description": "A card listing.",
                "grading": "",
                "card_condition": "Mint",
            },
        )

        item = Item.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{item.pk}")
        self.assertEqual(item.metadata, {"card_condition": "Mint"})
        self.assertNotIn("grading", item.metadata)

    def test_grading_is_stored_when_present(self):
        """Spec 03 case 17: a provided grading value is stored with card_condition."""
        self._login()

        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Graded Card",
                "description": "A graded card.",
                "grading": "PSA 10",
                "card_condition": "Mint",
            },
        )

        item = Item.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            item.metadata,
            {"grading": "PSA 10", "card_condition": "Mint"},
        )

    def _assert_box_error(self, value, message):
        self._login()
        response = self.client.post(
            "/listings/new",
            self._funko(box_condition=value),
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(message, _field_errors(html, "box_condition"))
        self.assertEqual(Item.objects.count(), 0)
        return html

    def test_box_condition_zero_uses_the_combined_range_message(self):
        """Spec 03 case 18: box_condition 0 shows the combined range message only."""
        html = self._assert_box_error("0", RANGE_MESSAGE)
        self.assertNotIn(MIN_ONLY, html)
        self.assertNotIn(MAX_ONLY, html)

    def test_box_condition_eleven_uses_the_combined_range_message(self):
        """Spec 03 case 18: box_condition 11 shows the combined range message only."""
        html = self._assert_box_error("11", RANGE_MESSAGE)
        self.assertNotIn(MIN_ONLY, html)
        self.assertNotIn(MAX_ONLY, html)

    def test_box_condition_text_is_rejected_as_not_a_whole_number(self):
        """Spec 03 case 18: box_condition abc shows Enter a whole number."""
        self._assert_box_error("abc", WHOLE_NUMBER)

    def test_box_condition_decimal_is_rejected_as_not_a_whole_number(self):
        """Spec 03 case 18: box_condition 7.5 shows Enter a whole number."""
        self._assert_box_error("7.5", WHOLE_NUMBER)

    def test_blank_card_condition_is_required(self):
        """Spec 03 case 19: a blank card_condition shows This field is required."""
        self._login()

        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Demo Card",
                "description": "A card listing.",
                "grading": "",
                "card_condition": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            REQUIRED,
            _field_errors(response.content.decode(), "card_condition"),
        )
        self.assertEqual(Item.objects.count(), 0)

    def test_card_condition_good_is_not_a_choice(self):
        """Spec 03 case 19: card_condition Good shows the choices message."""
        self._login()

        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Demo Card",
                "description": "A card listing.",
                "card_condition": "Good",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            GOOD_CHOICE,
            _field_errors(response.content.decode(), "card_condition"),
        )
        self.assertEqual(Item.objects.count(), 0)

    def test_blank_serial_number_is_required(self):
        """Spec 03 case 20: a blank serial_number shows This field is required."""
        self._login()

        response = self.client.post("/listings/new", self._funko(serial_number=""))

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "serial_number"))
        self.assertEqual(Item.objects.count(), 0)

    def test_missing_year_is_required(self):
        """Spec 03 case 20: a missing year shows This field is required."""
        self._login()

        response = self.client.post(
            "/listings/new",
            {
                "category": "lego",
                "title": "Demo Lego",
                "description": "A lego listing.",
                "sealed_misb": "on",
                "missing_parts": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "year"))
        self.assertEqual(Item.objects.count(), 0)

    def test_blank_title_is_required(self):
        """Spec 03 case 20: a blank title shows This field is required."""
        self._login()

        response = self.client.post("/listings/new", self._funko(title="   "))

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "title"))
        self.assertEqual(Item.objects.count(), 0)

    def test_blank_description_is_required(self):
        """Spec 03 case 20: a blank description shows This field is required."""
        self._login()

        response = self.client.post("/listings/new", self._funko(description=""))

        self.assertEqual(response.status_code, 200)
        self.assertIn(REQUIRED, _field_errors(response.content.decode(), "description"))
        self.assertEqual(Item.objects.count(), 0)

    def test_undeclared_character_input_is_ignored(self):
        """Spec 03 case 21: an undeclared character input is not written to metadata."""
        self._login()

        response = self.client.post(
            "/listings/new",
            self._funko(character="Batman"),
        )

        item = Item.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("character", item.metadata)
        self.assertEqual(
            set(item.metadata),
            {"box_condition", "original_box_included", "serial_number"},
        )

    def test_invalid_post_keeps_submitted_values(self):
        """Spec 03 case 22: an invalid funko post re-renders the submitted values."""
        self._login()

        response = self.client.post(
            "/listings/new",
            self._funko(
                title="Kept Title",
                description="Kept description",
                box_condition="11",
                original_box_included="on",
                serial_number="X",
            ),
        )

        html = response.content.decode()
        form = _post_form(html)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Item.objects.count(), 0)
        _kind, title, _body = _control(form, "title")
        self.assertIn('value="Kept Title"', title)
        _kind, _opening, description = _control(form, "description")
        self.assertIn("Kept description", description)
        _kind, box, _body = _control(form, "box_condition")
        self.assertIn('value="11"', box)
        _kind, checkbox, _body = _control(form, "original_box_included")
        self.assertIn("checked", checkbox)
        _kind, serial, _body = _control(form, "serial_number")
        self.assertIn('value="X"', serial)

    def test_post_without_csrf_token_is_rejected(self):
        """Spec 03 case 23: POST /listings/new without a CSRF token returns 403 and saves nothing."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post("/listings/new", self._funko())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Item.objects.count(), 0)

    def test_new_listing_link_is_absent_for_anonymous_visitors(self):
        """Spec 03 case 24: anonymous pages do not show the New listing link."""
        response = self.client.get("/")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("New listing", html)
        self.assertNotIn('href="/listings/new"', html)

    def test_new_listing_link_is_shown_when_logged_in(self):
        """Spec 03 case 24: a logged-in page shows New listing pointing at /listings/new."""
        self._login()

        response = self.client.get("/")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('<a href="/listings/new">New listing</a>', html)
