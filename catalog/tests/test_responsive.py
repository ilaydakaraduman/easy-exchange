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
        """Visual spec case 11: a card with no photo starts with the category illustration."""
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

        illustration = (
            '<img class="listing-photo listing-photo-placeholder" '
            'src="/static/img/placeholders/funko.svg" '
            'alt="Visible Title (Funko Pop & Figures)">'
        )
        self.assertTrue(card.startswith(illustration))
        after_title = card[card.index(title_link) + len(title_link):]
        self.assertLess(after_title.index("Funko Pop & Figures"), after_title.index("badge-available"))
        self.assertLess(after_title.index("badge-available"), after_title.index("Ada"))
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

    def test_illustrations_and_gradient_stay_local(self):
        """Visual spec case 10: SVGs and the page gradient use no remote asset."""
        css = (settings.BASE_DIR / "static" / "css" / "base.css").read_text(encoding="utf-8")

        for color in ("#f6f1e6", "#e5f3f2", "#f2faf6"):
            self.assertIn(color, css)
        self.assertIn('url("../img/placeholders/generic.svg")', css)
        self.assertIn("aspect-ratio: 4 / 3", css)
        self.assertIn("object-fit: cover", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotIn("url(http", css)
        self.assertNotIn("url(https", css)
        placeholders = settings.BASE_DIR / "static" / "img" / "placeholders"
        for name in ("funko.svg", "lego.svg", "tcg.svg", "generic.svg"):
            text = (placeholders / name).read_text(encoding="utf-8")
            self.assertIn("<svg", text)
            self.assertNotIn("<script", text.lower())
            self.assertNotIn("<image", text.lower())
            stripped = text.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http", stripped.lower())
