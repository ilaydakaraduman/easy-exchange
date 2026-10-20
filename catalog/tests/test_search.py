import re
from datetime import datetime, timezone as dt_timezone
from html import unescape

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import MVP_CATEGORIES

User = get_user_model()


def _cards(html):
    return re.findall(r'<li class="listing-card">(.*?)</li>', html, re.S)


def _titles(html):
    return [
        unescape(match.group(1).strip())
        for match in re.finditer(r'<a href="/listings/\d+">(.*?)</a>', html, re.S)
    ]


def _category_hrefs(html):
    nav = re.search(r'<nav class="filters"[^>]*>(.*?)</nav>', html, re.S).group(1)
    hrefs = []
    for attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", nav, re.S):
        href = re.search(r'href="([^"]*)"', attrs).group(1)
        hrefs.append((unescape(text.strip()), unescape(href)))
    return hrefs


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SearchTests(TestCase):
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

    def _item(self, slug, title, description="Plain description."):
        metadata = {
            "funko": {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-1",
            },
            "lego": {"sealed_misb": False, "missing_parts": False, "year": 2019},
            "tcg": {"card_condition": "Mint"},
        }[slug]
        return Item.objects.create(
            owner=self.owner,
            category=self.categories[slug],
            title=title,
            description=description,
            metadata=metadata,
        )

    def test_title_match_is_case_insensitive(self):
        """Spec 08 case 4: q matches a title regardless of case."""
        self._item("funko", "Amber Vase")
        self._item("lego", "Bronze Bowl")

        titles = _titles(self.client.get("/?q=amber").content.decode())

        self.assertEqual(titles, ["Amber Vase"])

    def test_description_match(self):
        """Spec 08 case 5: q matches a description when the title does not."""
        self._item("funko", "Plain Title", "Contains DEMO word")
        self._item("lego", "Other Title", "nope")

        titles = _titles(self.client.get("/?q=DEMO").content.decode())

        self.assertEqual(titles, ["Plain Title"])

    def test_search_combines_with_category_and_keeps_it_in_the_form(self):
        """Spec 08 case 6: q and category together return only that category."""
        self._item("funko", "Demo Funko")
        self._item("lego", "Demo Lego")

        html = self.client.get("/?q=demo&category=funko").content.decode()

        self.assertEqual(_titles(html), ["Demo Funko"])
        self.assertIn('name="q"', html)
        self.assertIn(">Search</button>", html)
        self.assertIn('name="category" value="funko"', html)

    def test_blank_q_does_not_filter(self):
        """Spec 08 case 7: a missing, empty, or whitespace q lists the same items."""
        self._item("funko", "First")
        self._item("lego", "Second")
        expected = _titles(self.client.get("/").content.decode())

        for url in ("/?q=", "/?q=%20%20"):
            with self.subTest(url=url):
                self.assertEqual(_titles(self.client.get(url).content.decode()), expected)
        self.assertEqual(
            _titles(self.client.get("/", {"q": "  "}).content.decode()),
            expected,
        )

    def test_matches_stay_newest_first(self):
        """Spec 08 case 8: search results keep newest-first order, then larger id."""
        older_low = self._item("funko", "Old low", "matchword")
        older_high = self._item("lego", "Old high", "matchword")
        newest = self._item("tcg", "New", "matchword")
        when = datetime(2024, 1, 1, tzinfo=dt_timezone.utc)
        Item.objects.filter(pk=older_low.pk).update(created_at=when)
        Item.objects.filter(pk=older_high.pk).update(created_at=when)
        Item.objects.filter(pk=newest.pk).update(
            created_at=datetime(2024, 6, 1, tzinfo=dt_timezone.utc)
        )

        titles = _titles(self.client.get("/?q=matchword").content.decode())

        self.assertEqual(titles, ["New", "Old high", "Old low"])

    def test_q_longer_than_100_characters_uses_the_first_100(self):
        """Spec 08 case 9: a q past 100 characters is cut and redisplayed at 100."""
        title = "A" * 100
        self._item("funko", title)

        html = self.client.get("/", {"q": title + "Z"}).content.decode()

        self.assertEqual(_titles(html), [title])
        self.assertIn(f'value="{title}"', html)
        self.assertNotIn(f'value="{title}Z"', html)

    def test_empty_search_uses_the_search_sentence(self):
        """Spec 08 case 10: a search with no rows uses the search empty sentence."""
        self._item("funko", "Something")
        missed = self.client.get("/?q=zzzznomatch").content.decode()
        self.assertIn("No listings match your search.", missed)
        self.assertNotIn("No listings yet.", missed)

        Item.objects.all().delete()
        empty = self.client.get("/").content.decode()
        self.assertIn("No listings yet.", empty)
        self.assertNotIn("No listings match your search.", empty)

    def test_search_text_is_escaped(self):
        """Spec 08 case 11: q and a matching title cannot inject a script tag."""
        raw = "<script>alert(1)</script>"
        self._item("funko", raw)

        html = self.client.get("/", {"q": raw}).content.decode()

        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_q_is_a_substring_match(self):
        """Spec 08 case 12: a SQL-looking q does not match items that lack that text."""
        self._item("funko", "Safe Title", "Nothing special")
        needle = "' OR 1=1 --"
        self._item("lego", "Quoted", f"Notes {needle} end")

        titles = _titles(self.client.get("/", {"q": needle}).content.decode())

        self.assertEqual(titles, ["Quoted"])

    def test_category_hrefs_gain_q_only_when_searching(self):
        """Spec 08 case 13: category hrefs stay as spec 04 unless q is non-blank."""
        home = _category_hrefs(self.client.get("/").content.decode())
        self.assertEqual(
            [href for _text, href in home],
            ["/", "/?category=funko", "/?category=lego", "/?category=tcg"],
        )

        searching = dict(_category_hrefs(self.client.get("/?q=ada").content.decode()))
        self.assertIn("category=funko", searching["Funko Pop & Figures"])
        self.assertIn("q=ada", searching["Funko Pop & Figures"])
