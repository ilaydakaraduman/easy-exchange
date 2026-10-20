import re
from html import unescape

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils.formats import date_format

from catalog.models import Category, Item
from catalog.schemas import FUNKO_SCHEMA, LEGO_SCHEMA, TCG_SCHEMA

User = get_user_model()

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def _details(html):
    section = html.split("<h2>Details</h2>", 1)[1]
    pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", section, re.S)
    return [(label.strip(), re.sub(r"\s+", " ", value).strip()) for label, value in pairs]


def _make_category(slug, name, schema):
    return Category.objects.create(slug=slug, name=name, metadata_schema=schema)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ListingDetailTests(TestCase):
    def setUp(self):
        self.funko = _make_category("funko", "Funko Pop & Figures", FUNKO_SCHEMA)
        self.lego = _make_category("lego", "Lego Sets & Minifigures", LEGO_SCHEMA)
        self.tcg = _make_category("tcg", "Trading Card Games", TCG_SCHEMA)
        self.owner = User.objects.create_user(
            email="alice@example.com",
            display_name="Alice",
            password="ExchangeDemo1!",
        )
        self.other = User.objects.create_user(
            email="bob@example.com",
            display_name="Bob",
            password="ExchangeDemo2!",
        )

    def _item(self, category, title, metadata, status=Item.Status.AVAILABLE, description="A public description."):
        return Item.objects.create(
            owner=self.owner,
            category=category,
            title=title,
            description=description,
            status=status,
            metadata=metadata,
        )

    def test_anonymous_detail_is_public(self):
        """Spec 04 case 12: an anonymous visitor gets 200 for an existing listing."""
        item = self._item(
            self.funko,
            "Public Funko",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

        response = self.client.get(f"/listings/{item.id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header("Location"))

    def test_logged_in_non_owner_detail_is_public(self):
        """Spec 04 case 12: a logged-in non-owner gets 200 for an existing listing."""
        item = self._item(
            self.funko,
            "Public Funko",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )
        self.client.force_login(self.other)

        response = self.client.get(f"/listings/{item.id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header("Location"))

    def test_missing_listing_returns_404(self):
        """Spec 04 case 13: GET /listings/999999 returns 404."""
        response = self.client.get("/listings/999999")

        self.assertEqual(response.status_code, 404)

    def test_funko_metadata_renders_in_schema_order(self):
        """Spec 04 case 14: funko details show 7, Yes, and FP-0001 under the schema labels."""
        item = self._item(
            self.funko,
            "Funko Item",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

        response = self.client.get(f"/listings/{item.id}")

        self.assertEqual(
            _details(response.content.decode()),
            [
                ("Box condition (1\u201310)", "7"),
                ("Original box included", "Yes"),
                ("Serial number", "FP-0001"),
            ],
        )

    def test_lego_metadata_renders_no_no_and_year(self):
        """Spec 04 case 14: lego details show No, No, and 2019."""
        item = self._item(
            self.lego,
            "Lego Item",
            {"sealed_misb": False, "missing_parts": False, "year": 2019},
        )

        response = self.client.get(f"/listings/{item.id}")

        self.assertEqual(
            _details(response.content.decode()),
            [
                ("Factory sealed (MISB)", "No"),
                ("Missing parts", "No"),
                ("Year", "2019"),
            ],
        )

    def test_absent_grading_renders_as_an_em_dash(self):
        """Spec 04 case 14: a tcg item without grading shows an em dash and Mint."""
        item = self._item(self.tcg, "Raw Card", {"card_condition": "Mint"})

        response = self.client.get(f"/listings/{item.id}")

        self.assertEqual(
            _details(response.content.decode()),
            [
                ("Grading (company and score)", "\u2014"),
                ("Card condition", "Mint"),
                ("Game", "\u2014"),
                ("Set name", "\u2014"),
            ],
        )

    def test_present_grading_renders_the_grade(self):
        """Spec 04 case 14: a tcg item with grading shows PSA 10."""
        item = self._item(
            self.tcg,
            "Graded Card",
            {"grading": "PSA 10", "card_condition": "Mint"},
        )

        response = self.client.get(f"/listings/{item.id}")

        self.assertEqual(
            _details(response.content.decode())[0],
            ("Grading (company and score)", "PSA 10"),
        )

    def test_core_fields_are_present(self):
        """Spec 04 case 15: the detail page shows title, category, owner, date, and description."""
        item = self._item(
            self.funko,
            "Core Title",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
            description="Readable description.",
        )

        response = self.client.get(f"/listings/{item.id}")

        html = unescape(response.content.decode())
        self.assertIn("Core Title", html)
        self.assertIn("Funko Pop & Figures", html)
        self.assertIn("Alice", html)
        self.assertIn(f"Listed on {date_format(item.created_at)}", html)
        self.assertIn("Readable description.", html)

    def test_description_script_is_escaped(self):
        """Spec 04 case 16: a description containing a script tag is escaped."""
        item = self._item(
            self.funko,
            "Unsafe Title",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
            description="<script>alert(1)</script>",
        )

        response = self.client.get(f"/listings/{item.id}")

        html = response.content.decode()
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_post_detail_returns_405_and_changes_nothing(self):
        """Spec 04 case 17: POST /listings/<id> returns 405 and leaves the item unchanged."""
        item = self._item(
            self.funko,
            "Still Here",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )
        before = (item.title, item.description, item.metadata, item.status)

        response = self.client.post(f"/listings/{item.id}")

        item.refresh_from_db()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            (item.title, item.description, item.metadata, item.status),
            before,
        )

    def test_badge_text_and_class_match_status_for_every_role(self):
        """Spec 04 case 18: every status shows its raw badge text and class to every role."""
        items = {
            Item.Status.AVAILABLE: self._item(
                self.funko,
                "Open",
                {
                    "box_condition": 7,
                    "original_box_included": True,
                    "serial_number": "FP-0001",
                },
                status=Item.Status.AVAILABLE,
            ),
            Item.Status.IN_TRADE: self._item(
                self.lego,
                "Locked",
                {"sealed_misb": False, "missing_parts": False, "year": 2019},
                status=Item.Status.IN_TRADE,
            ),
            Item.Status.TRADED: self._item(
                self.tcg,
                "Gone",
                {"card_condition": "Played"},
                status=Item.Status.TRADED,
            ),
        }
        viewers = {
            "anonymous": None,
            "non-owner": self.other,
            "owner": self.owner,
        }
        for status, item in items.items():
            for role, user in viewers.items():
                with self.subTest(status=status, role=role):
                    self.client.logout()
                    if user is not None:
                        self.client.force_login(user)
                    response = self.client.get(f"/listings/{item.id}")
                    html = response.content.decode()
                    css = status.lower()
                    self.assertIn(
                        f'<span class="badge badge-{css}">{status}</span>',
                        html,
                    )
                    for other in ("available", "in_trade", "traded"):
                        if other != css:
                            self.assertNotIn(f"badge-{other}", html)

    def test_owner_of_available_item_sees_edit_link(self):
        """Spec 04 case 19 / spec 03 case 32: the owner of an AVAILABLE listing sees Edit."""
        item = self._item(
            self.funko,
            "Mine",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )
        self.client.force_login(self.owner)

        response = self.client.get(f"/listings/{item.id}")

        self.assertIn(
            f'<a href="/listings/{item.id}/edit">Edit</a>',
            response.content.decode(),
        )

    def test_owner_of_in_trade_item_sees_no_edit_link(self):
        """Spec 04 case 19 / spec 03 case 32: the owner of an IN_TRADE listing sees no Edit link."""
        item = self._item(
            self.funko,
            "Locked mine",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
            status=Item.Status.IN_TRADE,
        )
        self.client.force_login(self.owner)

        response = self.client.get(f"/listings/{item.id}")

        self.assertNotIn(f"/listings/{item.id}/edit", response.content.decode())

    def test_owner_of_traded_item_sees_no_edit_link(self):
        """Spec 04 case 19 / spec 03 case 32: the owner of a TRADED listing sees no Edit link."""
        item = self._item(
            self.funko,
            "Gone mine",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
            status=Item.Status.TRADED,
        )
        self.client.force_login(self.owner)

        response = self.client.get(f"/listings/{item.id}")

        self.assertNotIn(f"/listings/{item.id}/edit", response.content.decode())

    def test_non_owner_sees_no_edit_link(self):
        """Spec 04 case 19 / spec 03 case 32: a non-owner sees no Edit link in any status."""
        item = self._item(
            self.funko,
            "Not mine",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )
        self.client.force_login(self.other)
        for status in (Item.Status.AVAILABLE, Item.Status.IN_TRADE, Item.Status.TRADED):
            with self.subTest(status=status):
                item.status = status
                item.save(update_fields=["status"])
                response = self.client.get(f"/listings/{item.id}")
                self.assertNotIn(f"/listings/{item.id}/edit", response.content.decode())

    def test_anonymous_visitor_sees_no_edit_link(self):
        """Spec 04 case 19 / spec 03 case 32: an anonymous visitor sees no Edit link in any status."""
        item = self._item(
            self.funko,
            "Public",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )
        for status in (Item.Status.AVAILABLE, Item.Status.IN_TRADE, Item.Status.TRADED):
            with self.subTest(status=status):
                item.status = status
                item.save(update_fields=["status"])
                response = self.client.get(f"/listings/{item.id}")
                self.assertNotIn(f"/listings/{item.id}/edit", response.content.decode())

    def test_anonymous_detail_shows_sign_in_link_and_no_action_form(self):
        """Spec 04 case 20: an anonymous detail page links to login and has no like or trade form."""
        item = self._item(
            self.funko,
            "Sign-in target",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

        response = self.client.get(f"/listings/{item.id}")

        html = response.content.decode()
        self.assertIn(
            f'<a href="/login?next=/listings/{item.id}">Sign in to like or trade</a>',
            html,
        )
        self.assertNotIn(f'action="/listings/{item.id}/like"', html)
        self.assertNotIn("/propose", html)
        self.assertNotIn('action="/trades/', html)

    def test_logged_in_detail_hides_the_sign_in_link_and_renders_listing_actions(self):
        """Spec 04 case 21: a logged-in detail page omits the sign-in link and renders listing_actions."""
        item = self._item(
            self.funko,
            "Actions",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )
        self.client.force_login(self.other)

        response = self.client.get(f"/listings/{item.id}")

        html = response.content.decode()
        self.assertNotIn("Sign in to like or trade", html)
        self.assertIn('class="listing-actions"', html)

    def test_brand_on_browse_links_home(self):
        """Spec 04 case 22: the header brand on the browse page links to /."""
        response = self.client.get("/")

        self.assertIn(
            '<a class="brand" href="/">Easy Exchange</a>',
            response.content.decode(),
        )

    def test_brand_on_detail_links_home(self):
        """Spec 04 case 22: the header brand on a detail page links to /."""
        item = self._item(
            self.funko,
            "Branded",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

        response = self.client.get(f"/listings/{item.id}")

        self.assertIn(
            '<a class="brand" href="/">Easy Exchange</a>',
            response.content.decode(),
        )

    def test_owner_email_never_appears_on_public_pages(self):
        """Spec 04 case 23: the owner's email is absent from browse and detail for every viewer."""
        items = [
            self._item(
                self.funko,
                "Funko privacy",
                {
                    "box_condition": 7,
                    "original_box_included": True,
                    "serial_number": "FP-0001",
                },
            ),
            self._item(
                self.lego,
                "Lego privacy",
                {"sealed_misb": True, "missing_parts": False, "year": 2020},
            ),
            self._item(
                self.tcg,
                "Card privacy",
                {"card_condition": "Near Mint"},
            ),
        ]
        paths = ["/", "/?category=funko"] + [f"/listings/{item.id}" for item in items]
        viewers = (None, self.other, self.owner)
        for path in paths:
            for viewer in viewers:
                with self.subTest(path=path, viewer=getattr(viewer, "email", "anonymous")):
                    self.client.logout()
                    if viewer is not None:
                        self.client.force_login(viewer)
                    response = self.client.get(path)
                    html = response.content.decode()
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("Alice", html)
                    self.assertNotIn("alice@example.com", html)
                    self.assertNotIn("bob@example.com", html)
                    self.assertIsNone(EMAIL_PATTERN.search(html))
