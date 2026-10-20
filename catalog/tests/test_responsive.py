import re
from html import unescape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import MVP_CATEGORIES

User = get_user_model()

HIDDEN_DESCRIPTION = "Hidden description text that must stay off the card."


def _cards(html):
    return re.findall(r'<li class="listing-card">(.*?)</li>', html, re.S)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ResponsiveTests(TestCase):
    def setUp(self):
        self.categories = {}
        for spec in MVP_CATEGORIES:
            self.categories[spec["slug"]] = Category.objects.create(
                slug=spec["slug"],
                name=spec["name"],
                metadata_schema=spec["metadata_schema"],
            )
        self.owner = User.objects.create_user(
            email="ada@example.com",
            display_name="Ada",
            password="ExchangeDemo1!",
        )

    def test_base_layout_has_one_viewport_meta(self):
        """Spec 08 case 1: the base layout has one viewport meta tag."""
        html = self.client.get("/").content.decode()

        self.assertEqual(html.count('name="viewport"'), 1)
        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            html,
        )

    def test_card_without_a_photo_starts_with_the_placeholder(self):
        """Spec 08 case 2: a card with no photo shows the placeholder and the spec 04 order."""
        item = Item.objects.create(
            owner=self.owner,
            category=self.categories["funko"],
            title="Visible Title",
            description=HIDDEN_DESCRIPTION,
            metadata={
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "HIDDEN-SERIAL-999",
            },
        )

        html = unescape(self.client.get("/").content.decode())
        card = _cards(html)[0].strip()
        title_link = f'<a href="/listings/{item.id}">Visible Title</a>'

        self.assertTrue(
            card.startswith(
                '<div class="listing-photo listing-photo-placeholder"></div>'
            )
        )
        self.assertNotIn("<img", card)
        self.assertLess(card.index(title_link), card.index("Funko Pop & Figures"))
        self.assertLess(card.index("Funko Pop & Figures"), card.index("badge-available"))
        self.assertLess(card.index("badge-available"), card.index("Ada"))
        self.assertNotIn(HIDDEN_DESCRIPTION, html)
        self.assertNotIn("HIDDEN-SERIAL-999", html)

    def test_stylesheet_defines_breakpoints_without_a_remote_url(self):
        """Spec 08 case 3: base.css has the column breakpoints and no remote url()."""
        css = (settings.BASE_DIR / "static" / "css" / "base.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("repeat(3, minmax(0, 1fr))", css)
        self.assertIn("@media (max-width: 960px)", css)
        self.assertIn("repeat(2, minmax(0, 1fr))", css)
        self.assertIn("@media (max-width: 639px)", css)
        self.assertIn("minmax(0, 1fr)", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("min-height: 44px", css)
        self.assertNotIn("url(http", css)
        self.assertNotIn("url(https", css)
        self.assertNotIn("<script", self.client.get("/").content.decode())
