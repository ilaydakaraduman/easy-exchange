import re
from datetime import datetime, timezone as dt_timezone
from html import unescape

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import MVP_CATEGORIES

User = get_user_model()

HIDDEN_DESCRIPTION = "Hidden description text that must stay off the card."
HIDDEN_SERIAL = "HIDDEN-SERIAL-999"


def _cards(html):
    return re.findall(r'<li class="listing-card">(.*?)</li>', html, re.S)


def _card_title(card):
    return re.search(r'<a href="/listings/\d+">(.*?)</a>', card, re.S).group(1).strip()


def _listing_rows(html):
    rows = []
    for card in _cards(html):
        title = _card_title(card)
        badge = re.search(r'class="badge [^"]+">([^<]+)', card).group(1).strip()
        rows.append((title, badge))
    return rows


def _filter_links(html):
    nav = re.search(r'<nav class="filters"[^>]*>(.*?)</nav>', html, re.S).group(1)
    links = []
    for attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", nav, re.S):
        href = re.search(r'href="([^"]*)"', attrs).group(1)
        links.append((unescape(text.strip()), href, 'aria-current="page"' in attrs))
    return links


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BrowseTests(TestCase):
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
        self.viewer = User.objects.create_user(
            email="ben@example.com",
            display_name="Ben",
            password="ExchangeDemo2!",
        )

    def _item(self, slug, title, status=Item.Status.AVAILABLE, **metadata):
        defaults = {
            "funko": {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": HIDDEN_SERIAL,
            },
            "lego": {"sealed_misb": False, "missing_parts": False, "year": 2019},
            "tcg": {"card_condition": "Mint"},
        }
        payload = dict(defaults[slug])
        payload.update(metadata)
        return Item.objects.create(
            owner=self.owner,
            category=self.categories[slug],
            title=title,
            description=HIDDEN_DESCRIPTION,
            status=status,
            metadata=payload,
        )

    def _stamp(self, item, when):
        Item.objects.filter(pk=item.pk).update(created_at=when)
        item.refresh_from_db()

    def test_browse_is_public_and_shows_the_same_items_to_a_logged_in_user(self):
        """Spec 04 case 1: anonymous and logged-in visitors both get 200 and the same listings."""
        self._item("funko", "First Funko")
        self._item("lego", "First Lego", status=Item.Status.IN_TRADE)

        anonymous = self.client.get("/")
        self.assertEqual(anonymous.status_code, 200)
        self.assertFalse(anonymous.has_header("Location"))

        self.client.force_login(self.viewer)
        logged_in = self.client.get("/")
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(
            _listing_rows(anonymous.content.decode()),
            _listing_rows(logged_in.content.decode()),
        )

    def test_listings_are_newest_first(self):
        """Spec 04 case 2: listings are ordered from newest created_at to oldest."""
        oldest = self._item("funko", "Oldest")
        middle = self._item("lego", "Middle")
        newest = self._item("tcg", "Newest")
        self._stamp(oldest, datetime(2024, 1, 1, tzinfo=dt_timezone.utc))
        self._stamp(middle, datetime(2024, 6, 1, tzinfo=dt_timezone.utc))
        self._stamp(newest, datetime(2024, 12, 1, tzinfo=dt_timezone.utc))

        response = self.client.get("/")

        titles = [_card_title(card) for card in _cards(response.content.decode())]
        self.assertEqual(titles, ["Newest", "Middle", "Oldest"])

    def test_equal_created_at_breaks_ties_by_larger_id_first(self):
        """Spec 04 case 3: when created_at matches, the larger id is listed first."""
        low = self._item("funko", "Low id")
        high = self._item("lego", "High id")
        self.assertLess(low.id, high.id)
        when = datetime(2024, 3, 1, tzinfo=dt_timezone.utc)
        self._stamp(low, when)
        self._stamp(high, when)

        response = self.client.get("/")

        titles = [_card_title(card) for card in _cards(response.content.decode())]
        self.assertEqual(titles, ["High id", "Low id"])

    def test_every_status_is_shown_with_its_badge_text(self):
        """Spec 04 case 4: AVAILABLE, IN_TRADE, and TRADED listings all appear with matching badges."""
        self._item("funko", "Open Funko", status=Item.Status.AVAILABLE)
        self._item("lego", "Locked Lego", status=Item.Status.IN_TRADE)
        self._item("tcg", "Gone Card", status=Item.Status.TRADED)

        response = self.client.get("/")

        rows = dict(_listing_rows(response.content.decode()))
        self.assertEqual(rows["Open Funko"], "AVAILABLE")
        self.assertEqual(rows["Locked Lego"], "IN_TRADE")
        self.assertEqual(rows["Gone Card"], "TRADED")

    def test_card_shows_title_category_badge_and_owner_only(self):
        """Spec 04 case 5: a card has the title link, category, badge, and display name, and nothing else."""
        item = self._item("funko", "Visible Title")

        response = self.client.get("/")

        html = unescape(response.content.decode())
        card = _cards(html)[0]
        title_link = f'<a href="/listings/{item.id}">Visible Title</a>'
        self.assertIn(title_link, card)
        self.assertIn("Funko Pop & Figures", card)
        self.assertIn('<span class="badge badge-available">AVAILABLE</span>', card)
        self.assertIn("Ada", card)
        after_title = card[card.index(title_link) + len(title_link):]
        self.assertLess(after_title.index("Funko Pop & Figures"), after_title.index("badge-available"))
        self.assertLess(after_title.index("badge-available"), after_title.index("Ada"))
        self.assertNotIn(HIDDEN_DESCRIPTION, html)
        self.assertNotIn(HIDDEN_SERIAL, html)
        self.assertNotIn(">Edit</a>", html)
        self.assertNotIn("<form", card)

    def test_category_filter_returns_only_that_slug(self):
        """Spec 04 case 6: each category filter lists exactly the two items in that category."""
        expected = {}
        for slug, label in (("funko", "Funko"), ("lego", "Lego"), ("tcg", "Card")):
            expected[slug] = {f"{label} One", f"{label} Two"}
            self._item(slug, f"{label} One")
            self._item(slug, f"{label} Two")

        for slug, titles in expected.items():
            with self.subTest(slug=slug):
                response = self.client.get(f"/?category={slug}")
                self.assertEqual(response.status_code, 200)
                shown = {_card_title(card) for card in _cards(response.content.decode())}
                self.assertEqual(shown, titles)

    def test_missing_all_and_empty_category_show_the_same_list(self):
        """Spec 04 case 7: /, ?category=all, and ?category= return the same listings."""
        self._item("funko", "Funko One")
        self._item("lego", "Lego One")
        self._item("tcg", "Card One")

        pages = [
            self.client.get("/"),
            self.client.get("/?category=all"),
            self.client.get("/?category="),
        ]

        lists = [_listing_rows(page.content.decode()) for page in pages]
        self.assertEqual(lists[0], lists[1])
        self.assertEqual(lists[1], lists[2])
        self.assertEqual(
            [title for title, _badge in lists[0]],
            ["Card One", "Lego One", "Funko One"],
        )

    def test_unknown_category_returns_404(self):
        """Spec 04 case 8: ?category=sports returns 404."""
        response = self.client.get("/?category=sports")

        self.assertEqual(response.status_code, 404)

    def test_filter_links_mark_only_the_active_one(self):
        """Spec 04 case 9: filter links are All then categories by slug, with aria-current on the active link."""
        home = self.client.get("/")
        lego = self.client.get("/?category=lego")

        expected = [
            ("All", "/", True),
            ("Funko Pop & Figures", "/?category=funko", False),
            ("Lego Sets & Minifigures", "/?category=lego", False),
            ("Trading Card Games", "/?category=tcg", False),
        ]
        self.assertEqual(_filter_links(home.content.decode()), expected)
        lego_links = _filter_links(lego.content.decode())
        self.assertEqual([link[:2] for link in lego_links], [link[:2] for link in expected])
        self.assertEqual(
            [link[2] for link in lego_links],
            [False, False, True, False],
        )

    def test_empty_browse_shows_no_listings_yet(self):
        """Spec 04 case 10: an empty item table shows No listings yet. and the filter links."""
        response = self.client.get("/")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("No listings yet.", html)
        self.assertEqual(len(_filter_links(html)), 4)

    def test_empty_category_shows_the_category_empty_state(self):
        """Spec 04 case 10: a category with no items shows No <name> listings yet."""
        self._item("funko", "Funko One")

        response = self.client.get("/?category=tcg")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("No Trading Card Games listings yet.", html)
        self.assertNotIn("Funko One", html)
        self.assertEqual(len(_filter_links(html)), 4)

    def test_browse_query_count_stays_bounded(self):
        """Spec 04 case 11: six listings render in two queries, not one query per card."""
        for number in range(6):
            slug = ("funko", "lego", "tcg")[number % 3]
            self._item(slug, f"Listing {number}")

        with self.assertNumQueries(2):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_cards(response.content.decode())), 6)
