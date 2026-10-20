import re
from html import unescape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import MVP_CATEGORIES

User = get_user_model()

SENTENCE = "List what you have and trade it one for one with another collector."
EMPTY_ALL = "No listings yet."
EMPTY_SEARCH = "No listings match your search."
EMPTY_TCG = "No Trading Card Games listings yet."


def _hero(html):
    start = html.index('<section class="hero">')
    end = html.index("</section>", start)
    return html[start:end]


def _filter_links(html):
    nav = re.search(r'<nav class="filters"[^>]*>(.*?)</nav>', html, re.S).group(1)
    links = []
    for attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", nav, re.S):
        href = re.search(r'href="([^"]*)"', attrs).group(1)
        links.append((unescape(text.strip()), href, 'aria-current="page"' in attrs))
    return links


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class VisualPolishPageTests(TestCase):
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

    def _item(self, title="Visible Title"):
        return Item.objects.create(
            owner=self.owner,
            category=self.categories["funko"],
            title=title,
            description="A public description.",
            metadata={
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

    def test_anonymous_hero_texts_and_links(self):
        """Spec 09 case 1: an anonymous home page leads with the hero and sign-up links."""
        html = self.client.get("/").content.decode()
        hero = _hero(html)
        steps = hero[hero.index("<ol"):]

        self.assertLess(html.index('<section class="hero">'), html.index('<nav class="filters"'))
        self.assertIn("Swap collectibles, not cash", hero)
        self.assertIn(SENTENCE, hero)
        self.assertIn('src="/static/img/hero.svg"', hero)
        self.assertIn('src="/static/img/steps/list.svg"', hero)
        self.assertIn('src="/static/img/steps/match.svg"', hero)
        self.assertIn('src="/static/img/steps/swap.svg"', hero)
        self.assertLess(steps.index("List an item"), steps.index("Match with collectors"))
        self.assertLess(steps.index("Match with collectors"), steps.index("Swap"))
        self.assertLess(hero.index('href="/register"'), hero.index('href="/login"'))
        self.assertIn('<a href="/register">Register</a>', hero)
        self.assertIn('<a href="/login">Sign in</a>', hero)
        self.assertNotIn('href="/listings/new"', hero)

    def test_logged_in_hero_offers_new_listing(self):
        """Spec 09 case 2: a logged-in hero offers New listing and no sign-in links."""
        self.client.force_login(self.owner)

        hero = _hero(self.client.get("/").content.decode())

        self.assertIn("Swap collectibles, not cash", hero)
        self.assertIn(SENTENCE, hero)
        self.assertIn('src="/static/img/hero.svg"', hero)
        self.assertIn("List an item", hero)
        self.assertIn("Match with collectors", hero)
        self.assertIn("Swap", hero)
        self.assertIn('<a href="/listings/new">New listing</a>', hero)
        self.assertNotIn('href="/login"', hero)
        self.assertNotIn('href="/register"', hero)

    def test_hero_has_no_form_or_trade_link(self):
        """Spec 09 case 3: the hero contains no form and no trade-route link."""
        pages = [self.client.get("/").content.decode()]
        self.client.force_login(self.owner)
        pages.append(self.client.get("/").content.decode())

        for html in pages:
            hero = _hero(html)
            self.assertNotIn("<form", hero)
            self.assertNotIn("/matches", hero)
            self.assertNotIn("/trades/", hero)
            self.assertNotIn("/propose", hero)

    def test_category_chip_links_stay_and_gain_icons(self):
        """Spec 09 case 4: category hrefs stay exact and icons sit outside the anchors."""
        html = self.client.get("/").content.decode()
        nav = re.search(r'<nav class="filters"[^>]*>(.*?)</nav>', html, re.S).group(1)

        self.assertEqual(
            _filter_links(html),
            [
                ("All", "/", True),
                ("Funko Pop & Figures", "/?category=funko", False),
                ("Lego Sets & Minifigures", "/?category=lego", False),
                ("Trading Card Games", "/?category=tcg", False),
            ],
        )
        for _attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", nav, re.S):
            self.assertNotIn("icons/", text)
            self.assertNotIn("<img", text)
        self.assertLess(nav.index("icons/figure.svg"), nav.index("Funko Pop &amp; Figures"))
        self.assertLess(nav.index("icons/brick.svg"), nav.index("Lego Sets"))
        self.assertLess(nav.index("icons/card.svg"), nav.index("Trading Card Games"))

        games = self.client.get("/?category=tcg").content.decode()
        game_nav = re.search(
            r'<nav class="game-filters"[^>]*>(.*?)</nav>',
            games,
            re.S,
        ).group(1)
        self.assertNotIn("icons/", game_nav)

    def test_detail_page_uses_two_columns(self):
        """Spec 09 case 8: the picture is left of the existing detail sequence."""
        item = self._item()

        anonymous = self.client.get(f"/listings/{item.id}").content.decode()
        self.client.force_login(self.owner)
        logged_in = self.client.get(f"/listings/{item.id}").content.decode()

        for html, action in (
            (anonymous, "Sign in to like or trade"),
            (logged_in, 'class="listing-actions"'),
        ):
            self.assertLess(html.index('class="detail-media"'), html.index('class="detail-main"'))
            media, main = html.split('class="detail-main"', 1)
            media = media.split('class="detail-media"', 1)[1]
            self.assertIn("listing-photo", media)
            self.assertIn("<h1>", main)
            self.assertIn("badge-available", main)
            self.assertIn("Ada", main)
            self.assertIn("Details", main)
            self.assertIn(action, main)

    def test_detail_layout_stacks_below_640px(self):
        """Spec 09 case 9: the detail grid is one column inside the 639px rule."""
        css = (settings.BASE_DIR / "static" / "css" / "base.css").read_text(encoding="utf-8")
        start = css.index("@media (max-width: 639px)")
        block = css[start:css.index("@media", start + 1)]

        self.assertIn(".detail-layout", block)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", block)

    def test_empty_browse_keeps_its_sentence(self):
        """Spec 09 case 10: an empty home shows No listings yet. under the drawing."""
        html = self.client.get("/").content.decode()

        self.assertIn(EMPTY_ALL, html)
        self.assertNotIn(EMPTY_SEARCH, html)
        self.assertNotIn(EMPTY_TCG, html)
        self.assertIn(
            '<img class="empty-art" alt="" src="/static/img/empty.svg">\n  <p>No listings yet.</p>',
            html,
        )

    def test_empty_category_keeps_its_sentence(self):
        """Spec 09 case 10: an empty category shows No <name> listings yet."""
        self._item("Funko One")

        html = self.client.get("/?category=tcg").content.decode()

        self.assertIn(EMPTY_TCG, html)
        self.assertNotIn(EMPTY_ALL, html)
        self.assertNotIn(EMPTY_SEARCH, html)
        self.assertIn(
            '<img class="empty-art" alt="" src="/static/img/empty.svg">\n'
            "  <p>No Trading Card Games listings yet.</p>",
            html,
        )

    def test_empty_search_keeps_its_sentence(self):
        """Spec 09 case 10: a search with no hits shows the search empty sentence."""
        self._item("Visible Title")

        html = self.client.get("/?q=zzzznotitle").content.decode()

        self.assertIn(EMPTY_SEARCH, html)
        self.assertNotIn(EMPTY_ALL, html)
        self.assertIn(
            '<img class="empty-art" alt="" src="/static/img/empty.svg">\n'
            "  <p>No listings match your search.</p>",
            html,
        )

    def test_browse_with_items_omits_the_empty_drawing(self):
        """Spec 09 case 10: a page with listings does not show the empty drawing."""
        self._item()

        html = self.client.get("/").content.decode()

        self.assertNotIn("/static/img/empty.svg", html)

    def test_favicon_link_is_present_once(self):
        """Spec 09 case 12: the head links the favicon once."""
        head = self.client.get("/").content.decode().split("</head>", 1)[0]

        self.assertEqual(head.count('rel="icon"'), 1)
        self.assertIn('href="/static/img/favicon.svg"', head)

    def test_new_svg_files_exist_and_placeholders_stay(self):
        """Spec 09 case 13: the new drawings are local SVG files and the placeholders remain."""
        paths = [
            "static/img/hero.svg",
            "static/img/steps/list.svg",
            "static/img/steps/match.svg",
            "static/img/steps/swap.svg",
            "static/img/icons/card.svg",
            "static/img/icons/brick.svg",
            "static/img/icons/figure.svg",
            "static/img/empty.svg",
            "static/img/favicon.svg",
        ]
        for rel in paths:
            text = (settings.BASE_DIR / rel).read_text(encoding="utf-8")
            lowered = text.lower()
            self.assertIn("<svg", lowered)
            self.assertNotIn("<script", lowered)
            self.assertNotIn("<image", lowered)
            stripped = lowered.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http", stripped)
        placeholders = settings.BASE_DIR / "static" / "img" / "placeholders"
        for name in ("funko.svg", "lego.svg", "tcg.svg", "generic.svg"):
            self.assertTrue((placeholders / name).is_file())

    def test_footer_is_on_home_and_login(self):
        """Spec 09 case 14: the base layout shows the class-project footer."""
        for path in ("/", "/login"):
            html = self.client.get(path).content.decode()
            self.assertIn("Easy Exchange, class project", html)
