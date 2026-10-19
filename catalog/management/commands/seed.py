from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Item
from catalog.schemas import MVP_CATEGORIES
from catalog.validators import validate_metadata, validate_metadata_schema
from trades.services import like_item

SUCCESS_LINE = "Seed complete: 3 categories, 2 users, 6 items, 1 match, 0 trades."

DEMO_USERS = (
    {
        "email": "ada@example.com",
        "display_name": "Ada",
        "password": "ExchangeDemo1!",
    },
    {
        "email": "ben@example.com",
        "display_name": "Ben",
        "password": "ExchangeDemo2!",
    },
)

DEMO_ITEMS = (
    (
        "ada@example.com",
        "funko",
        "Ada Funko Demo",
        "Demo Funko listing for Ada.",
        {
            "box_condition": 8,
            "original_box_included": True,
            "serial_number": "ADA-FUNKO-1",
        },
    ),
    (
        "ada@example.com",
        "lego",
        "Ada Lego Demo",
        "Demo Lego listing for Ada.",
        {
            "sealed_misb": True,
            "missing_parts": False,
            "year": 2021,
        },
    ),
    (
        "ada@example.com",
        "tcg",
        "Ada TCG Demo",
        "Demo TCG listing for Ada.",
        {
            "grading": "PSA 10",
            "card_condition": "Mint",
        },
    ),
    (
        "ben@example.com",
        "funko",
        "Ben Funko Demo",
        "Demo Funko listing for Ben.",
        {
            "box_condition": 4,
            "original_box_included": False,
            "serial_number": "BEN-FUNKO-1",
        },
    ),
    (
        "ben@example.com",
        "lego",
        "Ben Lego Demo",
        "Demo Lego listing for Ben.",
        {
            "sealed_misb": False,
            "missing_parts": True,
            "year": 2016,
        },
    ),
    (
        "ben@example.com",
        "tcg",
        "Ben TCG Demo",
        "Demo TCG listing for Ben.",
        {
            "card_condition": "Played",
        },
    ),
)


class Command(BaseCommand):
    help = "Load demo categories, users, listings, and one reciprocal match."

    def handle(self, *args, **options):
        with transaction.atomic():
            categories = _ensure_categories()
            users = _ensure_users()
            _ensure_items(categories, users)
            _ensure_likes(categories, users)
        self.stdout.write(SUCCESS_LINE)


def _ensure_categories():
    categories = {}
    for spec in MVP_CATEGORIES:
        category = Category.objects.filter(slug=spec["slug"]).first()
        if category is None:
            validate_metadata_schema(spec["metadata_schema"], slug=spec["slug"])
            category = Category.objects.create(
                slug=spec["slug"],
                name=spec["name"],
                metadata_schema=spec["metadata_schema"],
            )
        categories[spec["slug"]] = category
    return categories


def _ensure_users():
    User = get_user_model()
    users = {}
    for spec in DEMO_USERS:
        email = User.objects.normalize_email(spec["email"])
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                display_name=spec["display_name"],
                password=spec["password"],
            )
        users[email] = user
    return users


def _ensure_items(categories, users):
    for email, slug, title, description, metadata in DEMO_ITEMS:
        user = users[email]
        category = categories[slug]
        if Item.objects.filter(owner=user, category=category).exists():
            continue
        validate_metadata(category, metadata)
        Item.objects.create(
            owner=user,
            category=category,
            title=title,
            description=description,
            metadata=metadata,
        )


def _ensure_likes(categories, users):
    funko = categories["funko"]
    ada = users["ada@example.com"]
    ben = users["ben@example.com"]
    ada_funko = (
        Item.objects.filter(owner=ada, category=funko).order_by("id").first()
    )
    ben_funko = (
        Item.objects.filter(owner=ben, category=funko).order_by("id").first()
    )
    like_item(ada, ben_funko)
    like_item(ben, ada_funko)
