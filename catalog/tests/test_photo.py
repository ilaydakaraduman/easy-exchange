import tempfile
from importlib import reload
from io import BytesIO, StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import clear_url_caches
from PIL import Image

from catalog.models import Category, Item
from catalog.schemas import FUNKO_SCHEMA

User = get_user_model()


def _reload_urls():
    """Re-read the URLconf so the DEBUG media route matches the active settings."""
    import config.urls

    reload(config.urls)
    clear_url_caches()

FORMAT_MESSAGE = "Upload a JPEG, PNG, or WebP image."
SIZE_MESSAGE = "Image must be 5 MB or smaller."


def _image(fmt, name):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (20, 40, 60)).save(buffer, format=fmt)
    payload = buffer.getvalue()
    content_types = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
    }
    return payload, SimpleUploadedFile(name, payload, content_type=content_types[fmt])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PhotoTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.funko = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=FUNKO_SCHEMA,
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
        self.client.force_login(self.owner)

    def _data(self, **extra):
        data = {
            "category": "funko",
            "title": "Photo Funko",
            "description": "A listing with a photo.",
            "box_condition": "7",
            "original_box_included": "on",
            "serial_number": "FP-0001",
        }
        data.update(extra)
        return data

    def _files(self):
        return [path for path in Path(self.media.name).rglob("*") if path.is_file()]

    @override_settings(DEBUG=True)
    def test_jpeg_png_and_webp_are_stored_and_shown(self):
        """Spec 08 case 22: JPEG, PNG, and WebP uploads show on the card and the detail page."""
        _reload_urls()
        self.addCleanup(_reload_urls)
        for fmt, name in (("JPEG", "card.jpg"), ("PNG", "card.png"), ("WEBP", "card.webp")):
            with self.subTest(fmt=fmt):
                Item.objects.all().delete()
                payload, upload = _image(fmt, name)
                response = self.client.post(
                    "/listings/new",
                    {**self._data(title=f"{fmt} Funko"), "photo": upload},
                )

                self.assertEqual(response.status_code, 302)
                item = Item.objects.get()
                self.assertTrue(item.photo)
                self.assertNotIn("photo", item.metadata)
                for url in ("/", f"/listings/{item.id}"):
                    html = self.client.get(url).content.decode()
                    self.assertIn(
                        f'<img class="listing-photo" src="{item.photo.url}" alt="{fmt} Funko">',
                        html,
                    )
                fetched = self.client.get(item.photo.url)
                self.assertEqual(fetched.status_code, 200)
                body = b"".join(fetched.streaming_content)
                fetched.close()
                self.assertEqual(body, payload)

    def test_create_without_a_file_shows_the_placeholder(self):
        """Spec 08 case 23: a listing with no file keeps a blank photo and the placeholder."""
        response = self.client.post("/listings/new", self._data())

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get()
        self.assertFalse(item.photo)
        for url in ("/", f"/listings/{item.id}"):
            html = self.client.get(url).content.decode()
            self.assertIn("listing-photo listing-photo-placeholder", html)
            self.assertNotIn("<img", html)

    def test_rejected_files_are_not_stored(self):
        """Spec 08 case 24: a GIF, a fake PNG, and an oversize JPEG are rejected."""
        _payload, gif = _image("GIF", "card.gif")
        fake = SimpleUploadedFile("note.png", b"not an image", content_type="image/png")
        jpeg_payload, _jpeg = _image("JPEG", "big.jpg")
        oversize = SimpleUploadedFile(
            "big.jpg",
            jpeg_payload + b"0" * (5 * 1024 * 1024 + 1 - len(jpeg_payload)),
            content_type="image/jpeg",
        )
        cases = (
            (gif, FORMAT_MESSAGE),
            (fake, FORMAT_MESSAGE),
            (oversize, SIZE_MESSAGE),
        )
        for upload, message in cases:
            with self.subTest(name=upload.name):
                Item.objects.all().delete()
                response = self.client.post(
                    "/listings/new",
                    {**self._data(), "photo": upload},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(message, response.content.decode())
                self.assertEqual(Item.objects.count(), 0)
                self.assertEqual(self._files(), [])

    def test_edit_keeps_or_replaces_the_photo_while_available(self):
        """Spec 08 case 25: an empty file input keeps the photo; a new PNG replaces it."""
        _payload, png = _image("PNG", "first.png")
        self.client.post("/listings/new", {**self._data(), "photo": png})
        item = Item.objects.get()
        original_name = item.photo.name
        created_at = item.created_at

        kept = self.client.post(
            f"/listings/{item.id}/edit",
            self._data(title="Renamed"),
        )
        item.refresh_from_db()
        self.assertEqual(kept.status_code, 302)
        self.assertEqual(item.photo.name, original_name)
        self.assertEqual(item.title, "Renamed")

        _payload, replacement = _image("PNG", "second.png")
        replaced = self.client.post(
            f"/listings/{item.id}/edit",
            {**self._data(title="Renamed"), "photo": replacement},
        )
        item.refresh_from_db()
        self.assertEqual(replaced.status_code, 302)
        self.assertNotEqual(item.photo.name, original_name)
        self.assertEqual(item.status, Item.Status.AVAILABLE)
        self.assertEqual(item.owner_id, self.owner.id)
        self.assertEqual(item.category_id, self.funko.id)
        self.assertEqual(item.created_at, created_at)

    def test_edit_is_refused_when_not_available_or_not_owner(self):
        """Spec 08 case 26: a photo edit is refused for IN_TRADE and for a non-owner."""
        _payload, png = _image("PNG", "first.png")
        self.client.post("/listings/new", {**self._data(), "photo": png})
        item = Item.objects.get()
        original_name = item.photo.name
        item.status = Item.Status.IN_TRADE
        item.save(update_fields=["status"])
        _payload, new_file = _image("PNG", "second.png")

        locked = self.client.post(
            f"/listings/{item.id}/edit",
            {**self._data(), "photo": new_file},
        )
        item.refresh_from_db()
        self.assertEqual(locked.status_code, 403)
        self.assertIn(
            "This listing is in a trade and cannot be edited.",
            locked.content.decode(),
        )
        self.assertEqual(item.photo.name, original_name)

        item.status = Item.Status.AVAILABLE
        item.save(update_fields=["status"])
        self.client.force_login(self.other)
        _payload, outsider_file = _image("PNG", "third.png")
        outsider = self.client.post(
            f"/listings/{item.id}/edit",
            {**self._data(), "photo": outsider_file},
        )
        item.refresh_from_db()
        self.assertEqual(outsider.status_code, 403)
        self.assertIn("You can only edit your own listings.", outsider.content.decode())
        self.assertEqual(item.photo.name, original_name)

    def test_invalid_edit_does_not_store_the_new_photo(self):
        """Spec 08 case 27: a validation error leaves the stored photo unchanged."""
        _payload, png = _image("PNG", "first.png")
        self.client.post("/listings/new", {**self._data(), "photo": png})
        item = Item.objects.get()
        original_name = item.photo.name
        _payload, replacement = _image("PNG", "second.png")

        response = self.client.post(
            f"/listings/{item.id}/edit",
            {**self._data(box_condition="11"), "photo": replacement},
        )
        item.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(item.photo.name, original_name)
        self.assertEqual(item.title, "Photo Funko")
        self.assertEqual(item.metadata["box_condition"], 7)

    def test_seed_creates_no_photos(self):
        """Spec 08 case 28: seed leaves every item photo blank."""
        call_command("seed", stdout=StringIO())

        self.assertEqual(Item.objects.count(), 6)
        for item in Item.objects.all():
            self.assertFalse(item.photo)

    def test_media_route_is_registered_only_when_debug_is_true(self):
        """Spec 08 case 29: media serving is inside the DEBUG check."""
        source = (settings.BASE_DIR / "config" / "urls.py").read_text(encoding="utf-8")

        self.assertLess(source.index("if settings.DEBUG:"), source.index("static("))
