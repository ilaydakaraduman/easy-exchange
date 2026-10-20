import re
import tempfile
from io import BytesIO

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from PIL import Image

from catalog.models import Category
from trades.services import accept_trade, propose_trade
from trades.tests.test_matches_trades import _trade_sections
from trades.tests.test_propose import make_item, make_user, match_items

EMPTY_MATCHES = (
    "No matches yet. Like other collectors' listings — when they like "
    "one of yours back, the pair appears here."
)
PLACEHOLDER = "/static/img/placeholders/funko.svg"
ALT_CATEGORY = "(Funko Pop &amp; Figures)"


def _png():
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (20, 40, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class VisualPolishMatchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=[],
        )
        self.user_a = make_user("a@example.com", "User A")
        self.user_b = make_user("b@example.com", "User B")
        self.item_x = make_item(self.user_a, self.category, "Item X")
        self.item_y = make_item(self.user_b, self.category, "Item Y")

    def test_match_row_shows_both_thumbnails_and_the_arrow(self):
        """Spec 09 case 5: a photo-less pair shows two illustrations and a swap arrow."""
        match_items(self.item_x, self.item_y)
        self.client.force_login(self.user_a)

        html = self.client.get("/matches").content.decode()
        row = html.split('<li class="match-row">', 1)[1].split("</li>", 1)[0]
        your_link = row.index(f'href="/listings/{self.item_x.id}"')
        their_link = row.index(f'href="/listings/{self.item_y.id}"')
        arrow = row.index('class="swap-arrow"')

        self.assertEqual(row.count("<img"), 2)
        self.assertEqual(row.count(PLACEHOLDER), 2)
        self.assertLess(your_link, arrow)
        self.assertLess(arrow, their_link)
        self.assertIn('aria-hidden="true"', row)
        self.assertIn("Your item", row)
        self.assertIn("Their item", row)
        self.assertIn("Funko Pop &amp; Figures", row)
        self.assertIn(">AVAILABLE</span>", row)
        self.assertIn("Other owner User B", row)

    def test_match_row_uses_a_photo_when_one_item_has_one(self):
        """Spec 09 case 6: a stored photo replaces only that side's placeholder."""
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        match_items(self.item_x, self.item_y)
        self.client.force_login(self.user_a)

        with override_settings(MEDIA_ROOT=media.name):
            self.item_x.photo.save("side.png", ContentFile(_png()), save=True)
            html = self.client.get("/matches").content.decode()

        row = html.split('<li class="match-row">', 1)[1].split("</li>", 1)[0]
        images = re.findall(r'<img class="([^"]*)" src="([^"]*)" alt="([^"]*)">', row)

        self.assertEqual(len(images), 2)
        self.assertEqual(images[0][1], self.item_x.photo.url)
        self.assertNotIn("placeholder", images[0][0])
        self.assertEqual(images[0][2], f"Item X {ALT_CATEGORY}")
        self.assertEqual(images[1][1], PLACEHOLDER)
        self.assertIn("placeholder", images[1][0])
        self.assertEqual(images[1][2], f"Item Y {ALT_CATEGORY}")

    def test_trade_rows_show_thumbnails_and_keep_their_forms(self):
        """Spec 09 case 7: incoming, outgoing, and finished rows show both thumbnails."""
        match_items(self.item_x, self.item_y)
        trade = propose_trade(self.user_a, self.item_x, self.item_y)

        self.client.force_login(self.user_b)
        incoming, _outgoing, _finished = _trade_sections(self.client.get("/matches").content.decode())
        self.assertEqual(incoming.count("<img"), 2)
        self.assertIn(f'action="/trades/{trade.id}/accept"', incoming)
        self.assertIn(">Accept</button>", incoming)
        self.assertIn(f'action="/trades/{trade.id}/reject"', incoming)
        self.assertIn(">Reject</button>", incoming)

        self.client.force_login(self.user_a)
        _incoming, outgoing, _finished = _trade_sections(self.client.get("/matches").content.decode())
        self.assertEqual(outgoing.count("<img"), 2)
        self.assertIn(f'action="/trades/{trade.id}/cancel"', outgoing)
        self.assertIn(">Cancel</button>", outgoing)

        accept_trade(self.user_b, trade)
        _incoming, _outgoing, finished = _trade_sections(self.client.get("/matches").content.decode())
        self.assertEqual(finished.count("<img"), 2)
        self.assertNotIn("<form", finished)

    def test_matches_empty_states_keep_their_sentences(self):
        """Spec 09 case 11: an empty Matches page shows four drawings and the four sentences."""
        self.client.force_login(self.user_a)

        html = self.client.get("/matches").content.decode()

        self.assertIn(EMPTY_MATCHES, html)
        self.assertIn('<a href="/">Browse listings</a>', html)
        self.assertIn("No incoming proposals.", html)
        self.assertIn("No outgoing proposals.", html)
        self.assertIn("No finished trades.", html)
        self.assertEqual(html.count("/static/img/empty.svg"), 4)
