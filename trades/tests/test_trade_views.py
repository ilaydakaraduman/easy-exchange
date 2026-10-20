from django.test import Client, TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Match, Trade
from trades.services import accept_trade, propose_trade
from trades.tests.test_propose import make_item, make_user, match_items

NOT_IN_MATCH = "You are not part of this match."
LOCK_REFUSED = "One of these listings is no longer available."
ALREADY_RESOLVED = "This trade has already been resolved."
COUNTERPARTY_ONLY = "Only the counterparty can accept or reject this trade."
PROPOSER_ONLY = "Only the proposer can cancel this trade."


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class TradeViewTests(TestCase):
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
        self.item_z = make_item(self.user_c, self.category, "Item Z")

    def _snapshot(self):
        items = tuple(Item.objects.order_by("id").values_list("id", "status"))
        trades = tuple(
            Trade.objects.order_by("id").values_list(
                "id",
                "status",
                "item_offered_id",
                "item_requested_id",
                "proposer_id",
                "counterparty_id",
            )
        )
        return items, trades

    def _match(self):
        match_items(self.item_x, self.item_y)
        return Match.objects.get()

    def _proposed(self):
        match_items(self.item_x, self.item_y)
        return propose_trade(self.user_a, self.item_x, self.item_y)

    def _assert_login_redirect(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login")

    def test_anonymous_propose_redirects_to_login(self):
        """Spec 06 case 16: an anonymous propose redirects to /login and changes nothing."""
        match = self._match()
        before = self._snapshot()

        response = self.client.post(f"/matches/{match.id}/propose")

        self._assert_login_redirect(response)
        self.assertEqual(self._snapshot(), before)

    def test_anonymous_accept_redirects_to_login(self):
        """Spec 06 case 16: an anonymous accept redirects to /login and changes nothing."""
        trade = self._proposed()
        before = self._snapshot()

        response = self.client.post(f"/trades/{trade.id}/accept")

        self._assert_login_redirect(response)
        self.assertEqual(self._snapshot(), before)

    def test_anonymous_reject_redirects_to_login(self):
        """Spec 06 case 16: an anonymous reject redirects to /login and changes nothing."""
        trade = self._proposed()
        before = self._snapshot()

        response = self.client.post(f"/trades/{trade.id}/reject")

        self._assert_login_redirect(response)
        self.assertEqual(self._snapshot(), before)

    def test_anonymous_cancel_redirects_to_login(self):
        """Spec 06 case 16: an anonymous cancel redirects to /login and changes nothing."""
        trade = self._proposed()
        before = self._snapshot()

        response = self.client.post(f"/trades/{trade.id}/cancel")

        self._assert_login_redirect(response)
        self.assertEqual(self._snapshot(), before)

    def _assert_get_refused(self, url):
        before = self._snapshot()
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 405)
        self.client.force_login(self.user_a)
        logged_in = self.client.get(url)
        self.assertEqual(logged_in.status_code, 405)
        self.assertEqual(self._snapshot(), before)

    def test_get_propose_is_refused(self):
        """Spec 06 case 17: GET propose returns 405 and changes nothing."""
        match = self._match()
        self._assert_get_refused(f"/matches/{match.id}/propose")

    def test_get_accept_is_refused(self):
        """Spec 06 case 17: GET accept returns 405 and changes nothing."""
        trade = self._proposed()
        self._assert_get_refused(f"/trades/{trade.id}/accept")

    def test_get_reject_is_refused(self):
        """Spec 06 case 17: GET reject returns 405 and changes nothing."""
        trade = self._proposed()
        self._assert_get_refused(f"/trades/{trade.id}/reject")

    def test_get_cancel_is_refused(self):
        """Spec 06 case 17: GET cancel returns 405 and changes nothing."""
        trade = self._proposed()
        self._assert_get_refused(f"/trades/{trade.id}/cancel")

    def _assert_not_found(self, url):
        before = self._snapshot()
        self.client.force_login(self.user_a)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self._snapshot(), before)

    def test_unknown_match_returns_404(self):
        """Spec 06 case 18: proposing an unknown match returns 404."""
        self._assert_not_found("/matches/999999/propose")

    def test_unknown_accept_returns_404(self):
        """Spec 06 case 18: accepting an unknown trade returns 404."""
        self._assert_not_found("/trades/999999/accept")

    def test_unknown_reject_returns_404(self):
        """Spec 06 case 18: rejecting an unknown trade returns 404."""
        self._assert_not_found("/trades/999999/reject")

    def test_unknown_cancel_returns_404(self):
        """Spec 06 case 18: cancelling an unknown trade returns 404."""
        self._assert_not_found("/trades/999999/cancel")

    def _csrf_client(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        return client

    def test_propose_without_csrf_token_is_rejected(self):
        """Spec 06 case 19: propose without a CSRF token writes nothing."""
        match = self._match()
        before = self._snapshot()

        response = self._csrf_client(self.user_a).post(f"/matches/{match.id}/propose")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._snapshot(), before)

    def test_accept_without_csrf_token_is_rejected(self):
        """Spec 06 case 19: accept without a CSRF token writes nothing."""
        trade = self._proposed()
        before = self._snapshot()

        response = self._csrf_client(self.user_b).post(f"/trades/{trade.id}/accept")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._snapshot(), before)

    def test_reject_without_csrf_token_is_rejected(self):
        """Spec 06 case 19: reject without a CSRF token writes nothing."""
        trade = self._proposed()
        before = self._snapshot()

        response = self._csrf_client(self.user_b).post(f"/trades/{trade.id}/reject")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._snapshot(), before)

    def test_cancel_without_csrf_token_is_rejected(self):
        """Spec 06 case 19: cancel without a CSRF token writes nothing."""
        trade = self._proposed()
        before = self._snapshot()

        response = self._csrf_client(self.user_a).post(f"/trades/{trade.id}/cancel")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._snapshot(), before)

    def _assert_proposed_by(self, user, offered, requested, counterparty):
        trade = Trade.objects.get()
        self.assertEqual(trade.item_offered_id, offered.id)
        self.assertEqual(trade.item_requested_id, requested.id)
        self.assertEqual(trade.proposer_id, user.id)
        self.assertEqual(trade.counterparty_id, counterparty.id)
        self.assertEqual(trade.status, Trade.Status.PROPOSED)
        offered.refresh_from_db()
        requested.refresh_from_db()
        self.assertEqual(offered.status, Item.Status.IN_TRADE)
        self.assertEqual(requested.status, Item.Status.IN_TRADE)

    def test_propose_via_view_offers_the_actors_item(self):
        """Spec 06 case 20: the first owner proposes their own item."""
        match = self._match()
        self.client.force_login(self.user_a)

        response = self.client.post(f"/matches/{match.id}/propose")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/matches")
        self._assert_proposed_by(self.user_a, self.item_x, self.item_y, self.user_b)

    def test_propose_via_view_offers_the_other_owners_item(self):
        """Spec 06 case 20: the other owner proposes their own item."""
        match = self._match()
        self.client.force_login(self.user_b)

        response = self.client.post(f"/matches/{match.id}/propose")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/matches")
        self._assert_proposed_by(self.user_b, self.item_y, self.item_x, self.user_a)

    def test_non_member_propose_is_refused(self):
        """Spec 06 case 21: a user outside the match receives 403 and nothing changes."""
        match = self._match()
        before = self._snapshot()
        self.client.force_login(self.user_c)

        response = self.client.post(f"/matches/{match.id}/propose")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), NOT_IN_MATCH)
        self.assertEqual(self._snapshot(), before)

    def test_propose_of_in_trade_items_is_refused(self):
        """Spec 06 case 22: proposing a pair that is already IN_TRADE returns 409."""
        match = self._match()
        self.item_x.status = Item.Status.IN_TRADE
        self.item_y.status = Item.Status.IN_TRADE
        self.item_x.save(update_fields=["status"])
        self.item_y.save(update_fields=["status"])
        before = self._snapshot()
        self.client.force_login(self.user_a)

        response = self.client.post(f"/matches/{match.id}/propose")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content.decode(), LOCK_REFUSED)
        self.assertEqual(self._snapshot(), before)

    def test_propose_when_one_item_is_traded_is_refused(self):
        """Spec 06 case 22: proposing a pair with a TRADED item returns 409."""
        match = self._match()
        self.item_y.status = Item.Status.TRADED
        self.item_y.save(update_fields=["status"])
        before = self._snapshot()
        self.client.force_login(self.user_a)

        response = self.client.post(f"/matches/{match.id}/propose")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content.decode(), LOCK_REFUSED)
        self.assertEqual(self._snapshot(), before)

    def test_counterparty_accept_via_view(self):
        """Spec 06 case 23: the counterparty accept redirects and marks both items TRADED."""
        trade = self._proposed()
        self.client.force_login(self.user_b)

        response = self.client.post(f"/trades/{trade.id}/accept")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/matches")
        trade.refresh_from_db()
        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        self.assertEqual(trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_counterparty_reject_via_view(self):
        """Spec 06 case 23: the counterparty reject redirects and frees both items."""
        trade = self._proposed()
        self.client.force_login(self.user_b)

        response = self.client.post(f"/trades/{trade.id}/reject")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/matches")
        trade.refresh_from_db()
        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        self.assertEqual(trade.status, Trade.Status.REJECTED)
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)

    def test_proposer_cancel_via_view(self):
        """Spec 06 case 24: the proposer cancel redirects and frees both items."""
        trade = self._proposed()
        self.client.force_login(self.user_a)

        response = self.client.post(f"/trades/{trade.id}/cancel")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/matches")
        trade.refresh_from_db()
        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        self.assertEqual(trade.status, Trade.Status.CANCELLED)
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)

    def test_proposer_cannot_accept_or_reject(self):
        """Spec 06 case 25: the proposer receives 403 for accept and reject."""
        trade = self._proposed()
        before = self._snapshot()
        self.client.force_login(self.user_a)

        for action in ("accept", "reject"):
            with self.subTest(action=action):
                response = self.client.post(f"/trades/{trade.id}/{action}")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.content.decode(), COUNTERPARTY_ONLY)
                self.assertEqual(self._snapshot(), before)

    def test_counterparty_cannot_cancel(self):
        """Spec 06 case 25: the counterparty receives 403 for cancel."""
        trade = self._proposed()
        before = self._snapshot()
        self.client.force_login(self.user_b)

        response = self.client.post(f"/trades/{trade.id}/cancel")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), PROPOSER_ONLY)
        self.assertEqual(self._snapshot(), before)

    def test_third_user_cannot_resolve(self):
        """Spec 06 case 25: a third user receives 403 for accept, reject, and cancel."""
        trade = self._proposed()
        before = self._snapshot()
        self.client.force_login(self.user_c)
        expected = {
            "accept": COUNTERPARTY_ONLY,
            "reject": COUNTERPARTY_ONLY,
            "cancel": PROPOSER_ONLY,
        }

        for action, message in expected.items():
            with self.subTest(action=action):
                response = self.client.post(f"/trades/{trade.id}/{action}")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.content.decode(), message)
                self.assertEqual(self._snapshot(), before)

    def _assert_resolved_conflict(self, user, action):
        trade = self._proposed()
        accept_trade(self.user_b, trade)
        before = self._snapshot()
        self.client.force_login(user)

        response = self.client.post(f"/trades/{trade.id}/{action}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content.decode(), ALREADY_RESOLVED)
        self.assertEqual(self._snapshot(), before)

    def test_accept_of_resolved_trade_is_refused(self):
        """Spec 06 case 26: accepting an accepted trade returns 409."""
        self._assert_resolved_conflict(self.user_b, "accept")

    def test_reject_of_resolved_trade_is_refused(self):
        """Spec 06 case 26: rejecting an accepted trade returns 409."""
        self._assert_resolved_conflict(self.user_b, "reject")

    def test_cancel_of_resolved_trade_is_refused(self):
        """Spec 06 case 26: cancelling an accepted trade returns 409."""
        self._assert_resolved_conflict(self.user_a, "cancel")
