from django.test import Client, TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Like, Match
from trades.services import like_item
from trades.tests.test_propose import make_item, make_user

OWN_ITEM = "You cannot like your own listing."
ALREADY_TRADED = "This listing has already been traded."


def _listing_actions(html):
    marker = '<div class="listing-actions">'
    if marker not in html:
        raise AssertionError("listing_actions region is missing")
    start = html.index(marker)
    end = html.index("</div>", start)
    return html[start:end]


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class LikeViewTests(TestCase):
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

    def _like_url(self, item):
        return f"/listings/{item.id}/like"

    def test_anonymous_post_redirects_to_login_and_saves_nothing(self):
        """Spec 05 case 14: an anonymous like redirects to /login and writes nothing."""
        response = self.client.post(self._like_url(self.item_y))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login")
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(Match.objects.count(), 0)

    def test_get_like_route_is_refused(self):
        """Spec 05 case 15: GET /listings/<id>/like returns 405 for every visitor."""
        url = self._like_url(self.item_y)

        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 405)

        self.client.force_login(self.user_a)
        logged_in = self.client.get(url)
        self.assertEqual(logged_in.status_code, 405)
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(Match.objects.count(), 0)

    def test_missing_item_returns_404(self):
        """Spec 05 case 16: liking a missing listing returns 404 and creates no like."""
        self.client.force_login(self.user_a)

        response = self.client.post("/listings/999999/like")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Like.objects.count(), 0)

    def test_owner_like_is_refused(self):
        """Spec 05 case 17: the owner receives 403 and no like is created."""
        self.client.force_login(self.user_a)

        response = self.client.post(self._like_url(self.item_x))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), OWN_ITEM)
        self.assertEqual(Like.objects.count(), 0)

    def test_traded_item_via_view_is_refused(self):
        """Spec 05 case 18: liking a TRADED item through the view returns 403."""
        self.item_y.status = Item.Status.TRADED
        self.item_y.save(update_fields=["status"])
        self.client.force_login(self.user_a)

        response = self.client.post(self._like_url(self.item_y))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), ALREADY_TRADED)
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(Match.objects.count(), 0)

    def test_in_trade_item_via_view_is_liked(self):
        """Spec 05 case 19: liking an IN_TRADE item redirects back to the listing."""
        self.item_y.status = Item.Status.IN_TRADE
        self.item_y.save(update_fields=["status"])
        self.client.force_login(self.user_a)

        response = self.client.post(self._like_url(self.item_y))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{self.item_y.id}")
        self.assertEqual(Like.objects.filter(user=self.user_a, item=self.item_y).count(), 1)

    def test_valid_like_redirects_to_the_listing(self):
        """Spec 05 case 20: a new like redirects to the listing detail page."""
        self.client.force_login(self.user_a)

        response = self.client.post(self._like_url(self.item_y))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{self.item_y.id}")
        self.assertEqual(Like.objects.filter(user=self.user_a, item=self.item_y).count(), 1)
        self.assertEqual(Match.objects.count(), 0)

    def test_duplicate_like_via_view_redirects_again(self):
        """Spec 05 case 21: liking twice returns the same redirect and keeps one like."""
        self.client.force_login(self.user_a)
        url = self._like_url(self.item_y)
        self.client.post(url)

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/listings/{self.item_y.id}")
        self.assertNotIn(OWN_ITEM.encode(), response.content)
        self.assertNotIn(ALREADY_TRADED.encode(), response.content)
        self.assertEqual(Like.objects.filter(user=self.user_a, item=self.item_y).count(), 1)

    def test_match_is_created_through_two_view_posts(self):
        """Spec 05 case 22: reciprocal likes posted to the view create one ordered match."""
        self.client.force_login(self.user_b)
        self.client.post(self._like_url(self.item_x))
        self.client.force_login(self.user_a)
        self.client.post(self._like_url(self.item_y))

        match = Match.objects.get()
        self.assertEqual(match.item_a_id, min(self.item_x.id, self.item_y.id))
        self.assertEqual(match.item_b_id, max(self.item_x.id, self.item_y.id))

    def test_like_without_csrf_token_is_rejected(self):
        """Spec 05 case 23: a like POST without a CSRF token creates no like."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user_a)

        response = client.post(self._like_url(self.item_y))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(Match.objects.count(), 0)

    def _assert_like_button(self, item):
        self.client.force_login(self.user_a)
        response = self.client.get(f"/listings/{item.id}")
        self.assertEqual(response.status_code, 200)
        region = _listing_actions(response.content.decode())
        self.assertIn(
            f'<form method="post" action="/listings/{item.id}/like">',
            region,
        )
        self.assertIn('name="csrfmiddlewaretoken"', region)
        self.assertIn(">Like</button>", region)
        self.assertNotIn("Liked", region)

    def test_available_item_shows_like_button(self):
        """Spec 05 case 24: a not-yet-liked AVAILABLE item shows a Like form."""
        self._assert_like_button(self.item_y)

    def test_in_trade_item_shows_like_button(self):
        """Spec 05 case 24: a not-yet-liked IN_TRADE item shows a Like form."""
        self.item_y.status = Item.Status.IN_TRADE
        self.item_y.save(update_fields=["status"])
        self._assert_like_button(self.item_y)

    def test_traded_item_shows_no_like_control(self):
        """Spec 05 case 25: a not-yet-liked TRADED item shows nothing from this spec."""
        self.item_y.status = Item.Status.TRADED
        self.item_y.save(update_fields=["status"])
        self.client.force_login(self.user_a)

        response = self.client.get(f"/listings/{self.item_y.id}")

        html = response.content.decode()
        region = _listing_actions(html)
        self.assertNotIn("<form", region)
        self.assertNotIn(">Like</button>", region)
        self.assertNotIn("Liked", region)
        self.assertNotIn(ALREADY_TRADED, html)

    def test_liked_item_shows_liked_text(self):
        """Spec 05 case 26: after liking, the detail page shows Liked and no form."""
        like_item(self.user_a, self.item_y)
        self.client.force_login(self.user_a)

        response = self.client.get(f"/listings/{self.item_y.id}")

        region = _listing_actions(response.content.decode())
        self.assertIn("Liked", region)
        self.assertNotIn("<form", region)
        self.assertNotIn(">Like</button>", region)

    def test_liked_text_remains_after_the_item_is_traded(self):
        """Spec 05 case 26: Liked stays visible after the item becomes TRADED."""
        like_item(self.user_a, self.item_y)
        self.item_y.status = Item.Status.TRADED
        self.item_y.save(update_fields=["status"])
        self.client.force_login(self.user_a)

        response = self.client.get(f"/listings/{self.item_y.id}")

        region = _listing_actions(response.content.decode())
        self.assertIn("Liked", region)
        self.assertNotIn("<form", region)
        self.assertNotIn(">Like</button>", region)

    def test_liked_and_matched_shows_see_match_link(self):
        """Spec 05 case 27: a matched like is followed by a See match link."""
        like_item(self.user_b, self.item_x)
        like_item(self.user_a, self.item_y)
        self.client.force_login(self.user_a)

        response = self.client.get(f"/listings/{self.item_y.id}")

        region = _listing_actions(response.content.decode())
        self.assertLess(region.index("Liked"), region.index("See match"))
        self.assertIn('<a href="/matches">See match</a>', region)

    def test_liked_without_a_match_has_no_see_match_link(self):
        """Spec 05 case 27: a like with no match has no /matches href in the actions."""
        like_item(self.user_a, self.item_y)
        self.client.force_login(self.user_a)

        response = self.client.get(f"/listings/{self.item_y.id}")

        region = _listing_actions(response.content.decode())
        self.assertIn("Liked", region)
        self.assertNotIn('href="/matches"', region)
        self.assertNotIn("See match", region)

    def test_owner_sees_no_like_control(self):
        """Spec 05 case 28: the owner sees no like control in any status."""
        self.client.force_login(self.user_b)
        for status in (
            Item.Status.AVAILABLE,
            Item.Status.IN_TRADE,
            Item.Status.TRADED,
        ):
            with self.subTest(status=status):
                self.item_y.status = status
                self.item_y.save(update_fields=["status"])
                response = self.client.get(f"/listings/{self.item_y.id}")
                self.assertEqual(response.status_code, 200)
                region = _listing_actions(response.content.decode())
                self.assertNotIn("<form", region)
                self.assertNotIn("Liked", region)
                self.assertNotIn("See match", region)
                self.assertNotIn(">Like</button>", region)

    def test_anonymous_visitor_sees_no_like_control(self):
        """Spec 05 case 29: an anonymous visitor sees no like form and no Liked text."""
        response = self.client.get(f"/listings/{self.item_y.id}")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(f'action="/listings/{self.item_y.id}/like"', html)
        self.assertNotIn(">Like</button>", html)
        self.assertNotIn("Liked", html)
