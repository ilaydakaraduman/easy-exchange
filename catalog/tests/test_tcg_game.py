import re
from html import unescape
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import FUNKO_SCHEMA, LEGO_SCHEMA, TCG_SCHEMA
from catalog.validators import validate_metadata, validate_metadata_schema

User = get_user_model()


def _cards(html):
    return re.findall(r'<li class="listing-card">(.*?)</li>', html, re.S)


def _titles(html):
    return [
        unescape(match.group(1).strip())
        for match in re.finditer(r'<a href="/listings/\d+">(.*?)</a>', html, re.S)
    ]


def _nav_links(html, class_name):
    nav = re.search(rf'<nav class="{class_name}"[^>]*>(.*?)</nav>', html, re.S)
    if nav is None:
        return []
    links = []
    for attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", nav.group(1), re.S):
        href = re.search(r'href="([^"]*)"', attrs).group(1)
        links.append(
            (unescape(text.strip()), unescape(href), 'aria-current="page"' in attrs)
        )
    return links


def _details(html):
    section = html.split("<h2>Details</h2>", 1)[1]
    pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", section, re.S)
    return [(label.strip(), re.sub(r"\s+", " ", value).strip()) for label, value in pairs]


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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TcgGameTests(TestCase):
    def setUp(self):
        self.funko = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=FUNKO_SCHEMA,
        )
        self.lego = Category.objects.create(
            slug="lego",
            name="Lego Sets & Minifigures",
            metadata_schema=LEGO_SCHEMA,
        )
        self.tcg = Category.objects.create(
            slug="tcg",
            name="Trading Card Games",
            metadata_schema=TCG_SCHEMA,
        )
        self.owner = User.objects.create_user(
            email="ada@example.com",
            display_name="Ada",
            password="ExchangeDemo1!",
        )
        self.client.force_login(self.owner)

    def _item(self, category, title, metadata):
        return Item.objects.create(
            owner=self.owner,
            category=category,
            title=title,
            description="A demo listing.",
            metadata=metadata,
        )

    def test_seed_writes_the_extended_tcg_schema(self):
        """Spec 08 case 14: seed stores game and set_name and leaves item metadata unchanged."""
        Category.objects.all().delete()
        call_command("seed", stdout=StringIO())

        funko = Category.objects.get(slug="funko")
        lego = Category.objects.get(slug="lego")
        tcg = Category.objects.get(slug="tcg")
        self.assertEqual(funko.metadata_schema, FUNKO_SCHEMA)
        self.assertEqual(lego.metadata_schema, LEGO_SCHEMA)
        self.assertEqual(tcg.metadata_schema, TCG_SCHEMA)
        self.assertEqual(
            [entry["key"] for entry in tcg.metadata_schema],
            ["grading", "card_condition", "game", "set_name"],
        )
        self.assertEqual(
            tcg.metadata_schema[2]["choices"],
            ["Pokémon", "Magic: The Gathering", "Yu-Gi-Oh!", "Other"],
        )
        validate_metadata_schema(tcg.metadata_schema, slug="tcg")
        self.assertEqual(Item.objects.count(), 6)
        for item in Item.objects.select_related("category"):
            self.assertNotIn("game", item.metadata)
            self.assertNotIn("set_name", item.metadata)
            self.assertFalse(item.photo)
            validate_metadata(item.category, item.metadata)

    def test_create_and_edit_render_game_and_set_name(self):
        """Spec 08 case 15: TCG forms show optional game and set name; Funko does not."""
        created = self.client.get("/listings/new?category=tcg")
        html = created.content.decode()
        form = re.search(
            r'<form method="post" action="/listings/new"(.*?)</form>',
            html,
            re.S,
        ).group(1)
        names = [
            name
            for name in re.findall(r'name="([^"]+)"', form)
            if name != "csrfmiddlewaretoken"
        ]
        self.assertLess(names.index("card_condition"), names.index("game"))
        self.assertLess(names.index("game"), names.index("set_name"))
        _kind, game_opening, game_body = _control(form, "game")
        self.assertNotIn("required", game_opening)
        options = re.findall(r"<option\b([^>]*)>([^<]*)</option>", game_body)
        values = []
        for attrs, text in options:
            value = re.search(r'value="([^"]*)"', attrs)
            values.append((value.group(1) if value else "", text.strip()))
        self.assertEqual(
            values,
            [
                ("", ""),
                ("Pokémon", "Pokémon"),
                ("Magic: The Gathering", "Magic: The Gathering"),
                ("Yu-Gi-Oh!", "Yu-Gi-Oh!"),
                ("Other", "Other"),
            ],
        )
        _kind, set_opening, _body = _control(form, "set_name")
        self.assertNotIn("required", set_opening)

        item = self._item(self.tcg, "Raw Card", {"card_condition": "Mint"})
        edit = self.client.get(f"/listings/{item.id}/edit").content.decode()
        edit_form = re.search(
            rf'<form method="post" action="/listings/{item.id}/edit"(.*?)</form>',
            edit,
            re.S,
        ).group(1)
        _kind, _opening, edit_game = _control(edit_form, "game")
        self.assertIn('value=""', edit_game)
        _kind, set_name, _body = _control(edit_form, "set_name")
        self.assertNotRegex(set_name, r'value="[^"]+"')

        funko = self.client.get("/listings/new?category=funko").content.decode()
        self.assertNotIn('name="game"', funko)
        self.assertNotIn('name="set_name"', funko)

    def test_blank_game_and_set_name_are_omitted(self):
        """Spec 08 case 16: blank optional game and set name are omitted from metadata."""
        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Raw",
                "description": "A card.",
                "grading": "",
                "card_condition": "Mint",
                "game": "",
                "set_name": "   ",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get()
        self.assertEqual(item.metadata, {"card_condition": "Mint"})

    def test_invalid_game_choice_is_rejected(self):
        """Spec 08 case 16: a game outside the choices is rejected."""
        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Raw",
                "description": "A card.",
                "card_condition": "Mint",
                "game": "Good",
                "set_name": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Select a valid choice. Good is not one of the available choices.",
            response.content.decode(),
        )
        self.assertEqual(Item.objects.count(), 0)

    def test_game_and_set_name_are_stored(self):
        """Spec 08 case 16: a chosen game and a set name are stored."""
        response = self.client.post(
            "/listings/new",
            {
                "category": "tcg",
                "title": "Base Card",
                "description": "A card.",
                "card_condition": "Mint",
                "game": "Pokémon",
                "set_name": "Base",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Item.objects.get().metadata,
            {"card_condition": "Mint", "game": "Pokémon", "set_name": "Base"},
        )

    def test_detail_shows_absent_game_and_set_name_as_dashes(self):
        """Spec 08 case 17: missing game and set name render as an em dash."""
        item = self._item(self.tcg, "Raw Card", {"card_condition": "Mint"})

        details = _details(self.client.get(f"/listings/{item.id}").content.decode())

        self.assertEqual(
            details[-2:],
            [("Game", "\u2014"), ("Set name", "\u2014")],
        )

    def test_detail_shows_stored_game_and_set_name(self):
        """Spec 08 case 17: stored game and set name render on the detail page."""
        item = self._item(
            self.tcg,
            "Base Card",
            {"card_condition": "Mint", "game": "Pokémon", "set_name": "Base"},
        )

        details = dict(_details(self.client.get(f"/listings/{item.id}").content.decode()))

        self.assertEqual(details["Game"], "Pokémon")
        self.assertEqual(details["Set name"], "Base")

    def test_tcg_browse_shows_the_game_nav(self):
        """Spec 08 case 18: category=tcg shows the five game links after the category nav."""
        html = self.client.get("/?category=tcg").content.decode()
        links = _nav_links(html, "game-filters")

        self.assertEqual(
            [(text, href) for text, href, _current in links],
            [
                ("All games", "/?category=tcg"),
                ("Pokémon", "/?category=tcg&game=Pok%C3%A9mon"),
                (
                    "Magic: The Gathering",
                    "/?category=tcg&game=Magic%3A+The+Gathering",
                ),
                ("Yu-Gi-Oh!", "/?category=tcg&game=Yu-Gi-Oh%21"),
                ("Other", "/?category=tcg&game=Other"),
            ],
        )
        self.assertEqual([current for _text, _href, current in links], [True, False, False, False, False])
        self.assertEqual(len(_nav_links(html, "filters")), 4)

    def test_game_filter_matches_metadata_game(self):
        """Spec 08 case 19: a game link lists only TCG items with that metadata value."""
        self._item(
            self.tcg,
            "Pikachu",
            {"card_condition": "Mint", "game": "Pokémon"},
        )
        self._item(self.tcg, "Ungraded", {"card_condition": "Played"})

        filtered = self.client.get("/", {"category": "tcg", "game": "Pokémon"})
        self.assertEqual(_titles(filtered.content.decode()), ["Pikachu"])
        self.assertEqual(
            _titles(self.client.get("/?category=tcg").content.decode()),
            ["Ungraded", "Pikachu"],
        )

    def test_home_query_count_stays_two(self):
        """Spec 08 case 19: GET / still uses two queries for six listings."""
        for number in range(6):
            slug = ("funko", "lego", "tcg")[number % 3]
            category = {"funko": self.funko, "lego": self.lego, "tcg": self.tcg}[slug]
            metadata = {
                "funko": {
                    "box_condition": 7,
                    "original_box_included": True,
                    "serial_number": "FP-1",
                },
                "lego": {"sealed_misb": False, "missing_parts": False, "year": 2019},
                "tcg": {"card_condition": "Mint"},
            }[slug]
            self._item(category, f"Listing {number}", metadata)

        self.client.logout()
        with self.assertNumQueries(2):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_cards(response.content.decode())), 6)

    def test_unknown_game_returns_404(self):
        """Spec 08 case 20: a game value outside the choices is 404."""
        for params in (
            {"game": "Pokemon"},
            {"game": "Nope"},
            {"category": "funko", "game": "Nope"},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/", params).status_code, 404)

    def test_known_game_off_tcg_is_ignored(self):
        """Spec 08 case 21: a known game on a non-TCG category does not filter or 404."""
        self._item(
            self.funko,
            "Ada Funko",
            {
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-1",
            },
        )

        response = self.client.get("/", {"category": "funko", "game": "Pokémon"})
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(_titles(html), ["Ada Funko"])
        self.assertNotIn("game-filters", html)
