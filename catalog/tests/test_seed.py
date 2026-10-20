import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.validators import validate_metadata, validate_metadata_schema
from trades.models import Like, Match, Trade

User = get_user_model()

SUCCESS_LINE = "Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades.\n"

FUNKO_SCHEMA = [
    {
        "key": "box_condition",
        "label": "Box condition (1\u201310)",
        "type": "int",
        "required": True,
        "min": 1,
        "max": 10,
    },
    {
        "key": "original_box_included",
        "label": "Original box included",
        "type": "bool",
        "required": True,
    },
    {
        "key": "serial_number",
        "label": "Serial number",
        "type": "str",
        "required": True,
    },
]
LEGO_SCHEMA = [
    {
        "key": "sealed_misb",
        "label": "Factory sealed (MISB)",
        "type": "bool",
        "required": True,
    },
    {
        "key": "missing_parts",
        "label": "Missing parts",
        "type": "bool",
        "required": True,
    },
    {
        "key": "year",
        "label": "Year",
        "type": "int",
        "required": True,
    },
]
TCG_SCHEMA = [
    {
        "key": "grading",
        "label": "Grading (company and score)",
        "type": "str",
        "required": False,
    },
    {
        "key": "card_condition",
        "label": "Card condition",
        "type": "str",
        "required": True,
        "choices": ["Mint", "Near Mint", "Played"],
    },
]
EXPECTED_SCHEMAS = {
    "funko": FUNKO_SCHEMA,
    "lego": LEGO_SCHEMA,
    "tcg": TCG_SCHEMA,
}
EXPECTED_NAMES = {
    "funko": "Funko Pop & Figures",
    "lego": "Lego Sets & Minifigures",
    "tcg": "Trading Card Games",
}
EXPECTED_ITEMS = {
    ("ada@example.com", "funko"): (
        "Ada Funko Demo",
        "Demo Funko listing for Ada.",
        {
            "box_condition": 8,
            "original_box_included": True,
            "serial_number": "ADA-FUNKO-1",
        },
    ),
    ("ada@example.com", "lego"): (
        "Ada Lego Demo",
        "Demo Lego listing for Ada.",
        {"sealed_misb": True, "missing_parts": False, "year": 2021},
    ),
    ("ada@example.com", "tcg"): (
        "Ada TCG Demo",
        "Demo TCG listing for Ada.",
        {"grading": "PSA 10", "card_condition": "Mint"},
    ),
    ("ben@example.com", "funko"): (
        "Ben Funko Demo",
        "Demo Funko listing for Ben.",
        {
            "box_condition": 4,
            "original_box_included": False,
            "serial_number": "BEN-FUNKO-1",
        },
    ),
    ("ben@example.com", "lego"): (
        "Ben Lego Demo",
        "Demo Lego listing for Ben.",
        {"sealed_misb": False, "missing_parts": True, "year": 2016},
    ),
    ("ben@example.com", "tcg"): (
        "Ben TCG Demo",
        "Demo TCG listing for Ben.",
        {"card_condition": "Played"},
    ),
}


def _seed():
    out = StringIO()
    call_command("seed", stdout=out)
    return out.getvalue()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeedTests(TestCase):
    def test_seed_inserts_three_categories_with_the_exact_schemas(self):
        """Spec 07 case 1: seed inserts funko, lego, and tcg with the spec schemas and no sports."""
        _seed()

        self.assertEqual(Category.objects.count(), 3)
        self.assertFalse(Category.objects.filter(slug="sports").exists())
        for slug, schema in EXPECTED_SCHEMAS.items():
            category = Category.objects.get(slug=slug)
            self.assertEqual(category.name, EXPECTED_NAMES[slug])
            self.assertEqual(category.metadata_schema, schema)
            self.assertEqual(
                json.dumps(category.metadata_schema),
                json.dumps(schema),
            )
            validate_metadata_schema(category.metadata_schema, slug=slug)

    def test_seed_inserts_two_users_with_hashed_demo_passwords(self):
        """Spec 07 case 2: seed inserts Ada and Ben and stores password hashes, not plaintext."""
        _seed()

        self.assertEqual(User.objects.count(), 2)
        ada = User.objects.get(email="ada@example.com")
        ben = User.objects.get(email="ben@example.com")
        self.assertEqual(ada.display_name, "Ada")
        self.assertEqual(ben.display_name, "Ben")
        self.assertTrue(ada.check_password("ExchangeDemo1!"))
        self.assertTrue(ben.check_password("ExchangeDemo2!"))
        self.assertNotEqual(ada.password, "ExchangeDemo1!")
        self.assertNotEqual(ben.password, "ExchangeDemo2!")

    def test_seed_inserts_six_available_items_with_the_spec_metadata(self):
        """Spec 07 case 3: seed inserts six AVAILABLE items whose text and metadata match the tables."""
        _seed()

        self.assertEqual(Item.objects.count(), 6)
        for (email, slug), (title, description, metadata) in EXPECTED_ITEMS.items():
            item = Item.objects.get(owner__email=email, category__slug=slug)
            self.assertEqual(item.status, Item.Status.AVAILABLE)
            self.assertEqual(item.title, title)
            self.assertEqual(item.description, description)
            self.assertEqual(item.metadata, metadata)
            schema_keys = {entry["key"] for entry in item.category.metadata_schema}
            self.assertTrue(set(item.metadata).issubset(schema_keys))
            validate_metadata(item.category, item.metadata)
        ben_tcg = Item.objects.get(owner__email="ben@example.com", category__slug="tcg")
        self.assertNotIn("grading", ben_tcg.metadata)
        ada_tcg = Item.objects.get(owner__email="ada@example.com", category__slug="tcg")
        self.assertEqual(ada_tcg.metadata["grading"], "PSA 10")

    def test_seed_creates_one_ordered_funko_match_and_no_trades(self):
        """Spec 07 case 4: seed likes the two funko items, stores one ordered match, and no trades."""
        _seed()

        ada = User.objects.get(email="ada@example.com")
        ben = User.objects.get(email="ben@example.com")
        ada_funko = Item.objects.get(owner=ada, category__slug="funko")
        ben_funko = Item.objects.get(owner=ben, category__slug="funko")
        self.assertEqual(Like.objects.count(), 2)
        self.assertTrue(Like.objects.filter(user=ada, item=ben_funko).exists())
        self.assertTrue(Like.objects.filter(user=ben, item=ada_funko).exists())
        match = Match.objects.get()
        self.assertLess(match.item_a_id, match.item_b_id)
        self.assertEqual(
            {match.item_a_id, match.item_b_id},
            {ada_funko.id, ben_funko.id},
        )
        self.assertEqual(Trade.objects.count(), 0)
        self.assertFalse(Item.objects.exclude(status=Item.Status.AVAILABLE).exists())

    def test_seed_calls_like_item_and_does_not_insert_a_match_itself(self):
        """Spec 07 case 5: with like_item patched to a no-op, seed creates no like or match."""
        calls = []

        def record(user, item):
            calls.append((user, item))

        with patch("catalog.management.commands.seed.like_item", side_effect=record):
            _seed()

        self.assertEqual(Match.objects.count(), 0)
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(len(calls), 2)
        ada_funko = Item.objects.get(owner__email="ada@example.com", category__slug="funko")
        ben_funko = Item.objects.get(owner__email="ben@example.com", category__slug="funko")
        self.assertEqual(calls[0][0].email, "ada@example.com")
        self.assertEqual(calls[0][1].id, ben_funko.id)
        self.assertEqual(calls[1][0].email, "ben@example.com")
        self.assertEqual(calls[1][1].id, ada_funko.id)

    def test_second_seed_changes_nothing(self):
        """Spec 07 case 6: a second seed keeps counts, primary keys, hashes, item fields, and the success line."""
        first_out = _seed()
        category_ids = list(Category.objects.order_by("id").values_list("id", flat=True))
        user_ids = list(User.objects.order_by("id").values_list("id", flat=True))
        item_ids = list(Item.objects.order_by("id").values_list("id", flat=True))
        like_ids = list(Like.objects.order_by("id").values_list("id", flat=True))
        match_ids = list(Match.objects.order_by("id").values_list("id", flat=True))
        schemas = {
            category.slug: category.metadata_schema
            for category in Category.objects.all()
        }
        names = {category.slug: category.name for category in Category.objects.all()}
        users = {
            user.email: (user.display_name, user.password)
            for user in User.objects.all()
        }
        items = {
            item.pk: (item.title, item.description, item.metadata, item.status)
            for item in Item.objects.all()
        }

        second_out = _seed()

        self.assertEqual(Category.objects.count(), 3)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Item.objects.count(), 6)
        self.assertEqual(Like.objects.count(), 2)
        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(Trade.objects.count(), 0)
        self.assertEqual(
            list(Category.objects.order_by("id").values_list("id", flat=True)),
            category_ids,
        )
        self.assertEqual(
            list(User.objects.order_by("id").values_list("id", flat=True)),
            user_ids,
        )
        self.assertEqual(
            list(Item.objects.order_by("id").values_list("id", flat=True)),
            item_ids,
        )
        self.assertEqual(
            list(Like.objects.order_by("id").values_list("id", flat=True)),
            like_ids,
        )
        self.assertEqual(
            list(Match.objects.order_by("id").values_list("id", flat=True)),
            match_ids,
        )
        for category in Category.objects.all():
            self.assertEqual(category.metadata_schema, schemas[category.slug])
            self.assertEqual(category.name, names[category.slug])
        for user in User.objects.all():
            display_name, password = users[user.email]
            self.assertEqual(user.display_name, display_name)
            self.assertEqual(user.password, password)
        for item in Item.objects.all():
            self.assertEqual(
                (item.title, item.description, item.metadata, item.status),
                items[item.pk],
            )
        self.assertEqual(second_out, SUCCESS_LINE)
        self.assertEqual(first_out, second_out)
