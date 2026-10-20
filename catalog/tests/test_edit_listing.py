import re
from html import unescape

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from catalog.schemas import FUNKO_SCHEMA, TCG_SCHEMA

User = get_user_model()

OWN_LISTING = "You can only edit your own listings."
IN_TRADE = "This listing is in a trade and cannot be edited."


def _control(html, name):
    for match in re.finditer(r"<(input|textarea|select)\b([^>]*)>", html):
        opening = match.group(0)
        if f'name="{name}"' not in opening:
            continue
        kind = match.group(1)
        body = ""
        if kind in ("select", "textarea"):
            close = html.index(f"</{kind}>", match.end())
            body = html[match.end() : close]
        return kind, opening, body
    raise AssertionError(f"{name} was not rendered")


def _snapshot(item):
    item.refresh_from_db()
    return {
        "title": item.title,
        "description": item.description,
        "metadata": item.metadata,
        "status": item.status,
        "owner_id": item.owner_id,
        "category_id": item.category_id,
        "created_at": item.created_at,
    }


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EditListingTests(TestCase):
    def setUp(self):
        self.funko = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=FUNKO_SCHEMA,
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
        self.other = User.objects.create_user(
            email="ben@example.com",
            display_name="Ben",
            password="ExchangeDemo2!",
        )
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.funko,
            title="Demo Funko",
            description="A funko listing.",
            metadata={
                "box_condition": 7,
                "original_box_included": True,
                "serial_number": "FP-0001",
            },
        )

    def _edit_url(self, item=None):
        item = item or self.item
        return f"/listings/{item.pk}/edit"

    def _valid_post(self, **overrides):
        data = {
            "title": "Updated title",
            "description": "Updated description",
            "box_condition": "8",
            "original_box_included": "on",
            "serial_number": "FP-0002",
        }
        data.update(overrides)
        return data

    def test_anonymous_get_redirects_to_login_with_next(self):
        """Spec 03 case 25: anonymous GET edit redirects to /login?next=/listings/<id>/edit."""
        before = _snapshot(self.item)

        response = self.client.get(self._edit_url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/login?next=/listings/{self.item.pk}/edit",
        )
        self.assertEqual(_snapshot(self.item), before)

    def test_anonymous_post_redirects_to_login_without_next(self):
        """Spec 03 case 25: anonymous POST edit redirects to /login and leaves the item unchanged."""
        before = _snapshot(self.item)

        response = self.client.post(self._edit_url(), self._valid_post())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login")
        self.assertNotIn("next=", response["Location"])
        self.assertEqual(_snapshot(self.item), before)

    def test_non_owner_get_is_forbidden(self):
        """Spec 03 case 26: a non-owner GET returns 403 and leaves the item unchanged."""
        before = _snapshot(self.item)
        self.client.force_login(self.other)

        response = self.client.get(self._edit_url())

        self.assertEqual(response.status_code, 403)
        self.assertIn(OWN_LISTING, response.content.decode())
        self.assertEqual(_snapshot(self.item), before)

    def test_non_owner_post_is_forbidden(self):
        """Spec 03 case 26: a non-owner POST returns 403 and leaves the item unchanged."""
        before = _snapshot(self.item)
        self.client.force_login(self.other)

        response = self.client.post(self._edit_url(), self._valid_post())

        self.assertEqual(response.status_code, 403)
        self.assertIn(OWN_LISTING, response.content.decode())
        self.assertEqual(_snapshot(self.item), before)

    def _set_status(self, status):
        self.item.status = status
        self.item.save(update_fields=["status"])

    def test_owner_of_in_trade_item_cannot_get_the_edit_form(self):
        """Spec 03 case 27: the owner of an IN_TRADE item gets 403 on GET."""
        self._set_status(Item.Status.IN_TRADE)
        before = _snapshot(self.item)
        self.client.force_login(self.owner)

        response = self.client.get(self._edit_url())

        self.assertEqual(response.status_code, 403)
        self.assertIn(IN_TRADE, response.content.decode())
        self.assertNotIn('name="title"', response.content.decode())
        self.assertEqual(_snapshot(self.item), before)

    def test_owner_of_in_trade_item_cannot_post_an_edit(self):
        """Spec 03 case 27: the owner of an IN_TRADE item gets 403 on POST."""
        self._set_status(Item.Status.IN_TRADE)
        before = _snapshot(self.item)
        self.client.force_login(self.owner)

        response = self.client.post(self._edit_url(), self._valid_post())

        self.assertEqual(response.status_code, 403)
        self.assertIn(IN_TRADE, response.content.decode())
        self.assertEqual(_snapshot(self.item), before)

    def test_owner_of_traded_item_cannot_get_the_edit_form(self):
        """Spec 03 case 27: the owner of a TRADED item gets 403 on GET."""
        self._set_status(Item.Status.TRADED)
        before = _snapshot(self.item)
        self.client.force_login(self.owner)

        response = self.client.get(self._edit_url())

        self.assertEqual(response.status_code, 403)
        self.assertIn(IN_TRADE, response.content.decode())
        self.assertEqual(_snapshot(self.item), before)

    def test_owner_of_traded_item_cannot_post_an_edit(self):
        """Spec 03 case 27: the owner of a TRADED item gets 403 on POST."""
        self._set_status(Item.Status.TRADED)
        before = _snapshot(self.item)
        self.client.force_login(self.owner)

        response = self.client.post(self._edit_url(), self._valid_post())

        self.assertEqual(response.status_code, 403)
        self.assertIn(IN_TRADE, response.content.decode())
        self.assertEqual(_snapshot(self.item), before)

    def test_edit_form_is_prefilled_without_a_category_control(self):
        """Spec 03 case 28: the owner sees prefilled fields and the category as text only."""
        self.client.force_login(self.owner)

        response = self.client.get(self._edit_url())

        html = unescape(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Funko Pop & Figures", html)
        self.assertNotIn("<select", html)
        self.assertNotIn('name="category"', html)
        _kind, title, _body = _control(html, "title")
        self.assertIn('value="Demo Funko"', title)
        _kind, _opening, description = _control(html, "description")
        self.assertIn("A funko listing.", description)
        _kind, box, _body = _control(html, "box_condition")
        self.assertIn('value="7"', box)
        _kind, checkbox, _body = _control(html, "original_box_included")
        self.assertIn("checked", checkbox)
        _kind, serial, _body = _control(html, "serial_number")
        self.assertIn('value="FP-0001"', serial)

    def test_missing_grading_renders_as_an_empty_input(self):
        """Spec 03 case 28: a tcg item without grading shows an empty grading input."""
        item = Item.objects.create(
            owner=self.owner,
            category=self.tcg,
            title="Demo Card",
            description="A card listing.",
            metadata={"card_condition": "Mint"},
        )
        self.client.force_login(self.owner)

        response = self.client.get(self._edit_url(item))

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        _kind, grading, _body = _control(html, "grading")
        value = re.search(r'value="([^"]*)"', grading)
        self.assertTrue(value is None or value.group(1) == "")
        _kind, _opening, body = _control(html, "card_condition")
        mint = re.search(r'<option\b[^>]*value="Mint"[^>]*>', body)
        self.assertIsNotNone(mint)
        self.assertIn("selected", mint.group(0))

    def test_valid_edit_updates_only_title_description_and_metadata(self):
        """Spec 03 case 29: a valid edit updates those three fields and ignores category and status."""
        before = _snapshot(self.item)
        self.client.force_login(self.owner)

        response = self.client.post(
            self._edit_url(),
            self._valid_post(
                original_box_included="",
                category="lego",
                status="TRADED",
            ),
        )

        self.item.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{self.item.pk}")
        self.assertEqual(self.item.title, "Updated title")
        self.assertEqual(self.item.description, "Updated description")
        self.assertEqual(
            self.item.metadata,
            {
                "box_condition": 8,
                "original_box_included": False,
                "serial_number": "FP-0002",
            },
        )
        self.assertEqual(self.item.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item.owner_id, before["owner_id"])
        self.assertEqual(self.item.category_id, before["category_id"])
        self.assertEqual(self.item.created_at, before["created_at"])

    def test_invalid_edit_leaves_the_item_unchanged(self):
        """Spec 03 case 30: an invalid edit re-renders the error and does not write the item."""
        before = _snapshot(self.item)
        self.client.force_login(self.owner)

        response = self.client.post(
            self._edit_url(),
            self._valid_post(title="Should not stick", box_condition="11"),
        )

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ensure this value is between 1 and 10.", html)
        self.assertEqual(_snapshot(self.item), before)

    def test_stale_edit_after_status_change_is_refused(self):
        """Spec 03 case 31: a post after the item leaves AVAILABLE returns 403 and writes nothing."""
        self.client.force_login(self.owner)
        form = self.client.get(self._edit_url())
        self.assertEqual(form.status_code, 200)
        self._set_status(Item.Status.IN_TRADE)
        before = _snapshot(self.item)

        response = self.client.post(self._edit_url(), self._valid_post())

        self.assertEqual(response.status_code, 403)
        self.assertIn(IN_TRADE, response.content.decode())
        self.assertEqual(_snapshot(self.item), before)
