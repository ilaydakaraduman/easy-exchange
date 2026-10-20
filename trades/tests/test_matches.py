import re
from html import escape

from django.test import TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Like, Match, Trade
from trades.tests.test_propose import make_item, make_user, match_items

EMPTY_STATE = (
    "No matches yet. Like other collectors' listings — when they like "
    "one of yours back, the pair appears here."
)


def _match_rows(html):
    rows = []
    for part in html.split('<li class="match-row">')[1:]:
        rows.append(part.split("</li>", 1)[0])
    return rows


def _your_item_title(row):
    your = row.split("Their item", 1)[0]
    match = re.search(r'href="/listings/\d+">([^<]*)</a>', your)
    if match is None:
        raise AssertionError("your item title link is missing")
    return match.group(1)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class MatchesPageTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=[],
        )
        self.user_a = make_user("a@example.com", "User A")
        self.user_b = make_user("b@example.com", "User B")
        self.user_c = make_user("c@example.com", "User C")
        self.item_x = make_item(self.user_a, self.category, "Item X")
        self.item_y = make_item(self.user_b, self.category, "Item Y")

    def _snapshot(self):
        return (
            tuple(Item.objects.order_by("id").values_list("id", "status")),
            Like.objects.count(),
            Match.objects.count(),
            Trade.objects.count(),
        )

    def test_anonymous_get_redirects_to_login_with_next(self):
        """Spec 05 case 30: an anonymous visitor is sent to /login?next=/matches."""
        match_items(self.item_x, self.item_y)

        response = self.client.get("/matches")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login?next=/matches")
        self.assertTemplateNotUsed(response, "trades/matches.html")
        self.assertNotIn(EMPTY_STATE, response.content.decode())

    def test_empty_state(self):
        """Spec 05 case 31: a user with no matches sees the empty state."""
        self.client.force_login(self.user_a)

        response = self.client.get("/matches")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>Matches</h1>", html)
        self.assertIn(EMPTY_STATE, html)
        self.assertIn('<a href="/">Browse listings</a>', html)
        self.assertNotIn('class="match-row"', html)

    def _assert_pair_row(self, html, your_item, their_item, other_name, hidden_email):
        self.assertNotIn(hidden_email, html)
        rows = _match_rows(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        your, their = row.split("Their item", 1)
        self.assertIn("Your item", your)
        self.assertIn(f'href="/listings/{your_item.id}"', your)
        self.assertIn(your_item.title, your)
        self.assertIn(escape(your_item.category.name), your)
        self.assertIn(f'class="badge badge-{your_item.status.lower()}"', your)
        self.assertIn(f">{your_item.status}</span>", your)
        self.assertIn(f'href="/listings/{their_item.id}"', their)
        self.assertIn(their_item.title, their)
        self.assertIn(escape(their_item.category.name), their)
        self.assertIn(f'class="badge badge-{their_item.status.lower()}"', their)
        self.assertIn(f">{their_item.status}</span>", their)
        self.assertIn(other_name, row)

    def test_pair_rendered_for_the_first_owner(self):
        """Spec 05 case 32: the first owner sees their item on the left of the pair."""
        match_items(self.item_x, self.item_y)
        self.client.force_login(self.user_a)

        response = self.client.get("/matches")

        self.assertEqual(response.status_code, 200)
        self._assert_pair_row(
            response.content.decode(),
            self.item_x,
            self.item_y,
            self.user_b.display_name,
            self.user_b.email,
        )

    def test_pair_rendered_for_the_other_owner(self):
        """Spec 05 case 32: the other owner sees the same pair with the sides swapped."""
        match_items(self.item_x, self.item_y)
        self.client.force_login(self.user_b)

        response = self.client.get("/matches")

        self.assertEqual(response.status_code, 200)
        self._assert_pair_row(
            response.content.decode(),
            self.item_y,
            self.item_x,
            self.user_a.display_name,
            self.user_a.email,
        )

    def test_third_user_does_not_see_the_pair(self):
        """Spec 05 case 33: a user who owns neither item sees the empty state."""
        match_items(self.item_x, self.item_y)
        self.client.force_login(self.user_c)

        response = self.client.get("/matches")

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(EMPTY_STATE, html)
        self.assertNotIn(self.item_x.title, html)
        self.assertNotIn(self.item_y.title, html)
        self.assertNotIn('class="match-row"', html)

    def test_matches_are_ordered_by_id(self):
        """Spec 05 case 34: match rows appear in ascending Match.id order."""
        titles = []
        for number in (1, 2, 3):
            partner = make_user(f"partner{number}@example.com", f"Partner {number}")
            mine = make_item(self.user_a, self.category, f"Mine {number}")
            theirs = make_item(partner, self.category, f"Theirs {number}")
            match_items(mine, theirs)
            titles.append(mine.title)
        self.assertEqual(Match.objects.count(), 3)
        self.client.force_login(self.user_a)

        response = self.client.get("/matches")

        rows = _match_rows(response.content.decode())
        self.assertEqual([_your_item_title(row) for row in rows], titles)

    def test_in_trade_pair_is_still_listed(self):
        """Spec 05 case 35: an IN_TRADE pair stays listed with its stored badge."""
        match_items(self.item_x, self.item_y)
        self.item_x.status = Item.Status.IN_TRADE
        self.item_x.save(update_fields=["status"])
        self.client.force_login(self.user_a)

        response = self.client.get("/matches")

        rows = _match_rows(response.content.decode())
        self.assertEqual(len(rows), 1)
        your, their = rows[0].split("Their item", 1)
        self.assertIn('class="badge badge-in_trade">IN_TRADE</span>', your)
        self.assertIn('class="badge badge-available">AVAILABLE</span>', their)

    def test_traded_pair_is_still_listed(self):
        """Spec 05 case 35: a pair with a TRADED item stays listed with that badge."""
        match_items(self.item_x, self.item_y)
        self.item_x.status = Item.Status.TRADED
        self.item_x.save(update_fields=["status"])
        self.client.force_login(self.user_a)

        response = self.client.get("/matches")

        rows = _match_rows(response.content.decode())
        self.assertEqual(len(rows), 1)
        your, their = rows[0].split("Their item", 1)
        self.assertIn('class="badge badge-traded">TRADED</span>', your)
        self.assertIn('class="badge badge-available">AVAILABLE</span>', their)

    def test_reserved_blocks_are_present(self):
        """Spec 05 case 36: each row has match_actions and the page has matches_trades."""
        match_items(self.item_x, self.item_y)
        self.client.force_login(self.user_a)

        response = self.client.get("/matches")

        html = response.content.decode()
        rows = _match_rows(html)
        self.assertEqual(len(rows), 1)
        self.assertIn('class="match_actions"', rows[0])
        self.assertIn('class="matches_trades"', html)
        self.assertLess(html.index('class="match-row"'), html.index('class="matches_trades"'))

    def test_post_matches_is_refused(self):
        """Spec 05 case 37: POST /matches returns 405 and changes nothing."""
        match_items(self.item_x, self.item_y)
        before = self._snapshot()

        anonymous = self.client.post("/matches")
        self.assertEqual(anonymous.status_code, 405)

        self.client.force_login(self.user_a)
        logged_in = self.client.post("/matches")
        self.assertEqual(logged_in.status_code, 405)
        self.assertEqual(self._snapshot(), before)

    def test_matches_page_query_count_is_bounded(self):
        """Spec 05 case 38: six matches render with a bounded query count."""
        for number in range(6):
            partner = make_user(f"partner{number}@example.com", f"Partner {number}")
            mine = make_item(self.user_a, self.category, f"Mine {number}")
            theirs = make_item(partner, self.category, f"Theirs {number}")
            match_items(mine, theirs)
        self.client.force_login(self.user_a)

        with self.assertNumQueries(4):
            response = self.client.get("/matches")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_match_rows(response.content.decode())), 6)

    def test_matches_link_is_shown_only_when_logged_in(self):
        """Spec 05 case 39: the header Matches link is present only for a logged-in user."""
        anonymous = self.client.get("/")
        self.assertEqual(anonymous.status_code, 200)
        self.assertNotIn('href="/matches"', anonymous.content.decode())

        self.client.force_login(self.user_a)
        logged_in = self.client.get("/")
        self.assertEqual(logged_in.status_code, 200)
        self.assertIn('<a href="/matches">Matches</a>', logged_in.content.decode())
