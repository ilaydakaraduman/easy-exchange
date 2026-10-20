from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Trade
from trades.services import (
    TradeConflict,
    TradeInvariantError,
    TradeNotAllowed,
    accept_trade,
    cancel_trade,
    like_item,
    propose_trade,
    reject_trade,
)

User = get_user_model()

ALREADY_RESOLVED = "This trade has already been resolved."
COUNTERPARTY_ONLY = "Only the counterparty can accept or reject this trade."
PROPOSER_ONLY = "Only the proposer can cancel this trade."


def make_user(email, display_name):
    return User.objects.create_user(
        email=email,
        display_name=display_name,
        password="ExchangeDemo1!",
    )


def make_item(owner, category, title):
    return Item.objects.create(
        owner=owner,
        category=category,
        title=title,
        description="Demo listing",
        metadata={},
    )


def match_items(left, right):
    """Create the Match for this pair through reciprocal likes."""
    like_item(right.owner, left)
    like_item(left.owner, right)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class ResolveTradeTests(TestCase):
    def setUp(self):
        category = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=[],
        )
        self.user_a = make_user("a@example.com", "User A")
        self.user_b = make_user("b@example.com", "User B")
        self.user_c = make_user("c@example.com", "User C")
        self.item_x = make_item(self.user_a, category, "Item X")
        self.item_y = make_item(self.user_b, category, "Item Y")
        match_items(self.item_x, self.item_y)
        self.trade = propose_trade(self.user_a, self.item_x, self.item_y)

    def _assert_raises_exact(self, exc_class, message, func):
        with self.assertRaises(exc_class) as raised:
            func()
        self.assertEqual(str(raised.exception), message)

    def _reload(self):
        self.trade.refresh_from_db()
        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()

    def _assert_still_proposed(self):
        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.PROPOSED)
        self.assertEqual(self.item_x.status, Item.Status.IN_TRADE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)
        self.assertEqual(self.trade.created_at, self.trade.updated_at)
        self.assertEqual(Trade.objects.count(), 1)

    def test_accept_marks_trade_accepted_and_items_traded(self):
        """Spec 06 case 3: the counterparty accept is terminal for both items."""
        created_at = self.trade.created_at

        accepted = accept_trade(self.user_b, self.trade)

        self._reload()
        self.assertEqual(accepted.pk, self.trade.pk)
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.created_at, created_at)
        self.assertGreater(self.trade.updated_at, self.trade.created_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_second_accept_on_an_accepted_trade_is_refused(self):
        """Spec 06 case 3: accepting an accepted trade changes nothing."""
        accept_trade(self.user_b, self.trade)
        self._reload()
        updated_at = self.trade.updated_at

        self._assert_raises_exact(
            TradeConflict,
            ALREADY_RESOLVED,
            lambda: accept_trade(self.user_b, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.updated_at, updated_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_reject_on_an_accepted_trade_is_refused(self):
        """Spec 06 case 3: rejecting an accepted trade changes nothing."""
        accept_trade(self.user_b, self.trade)
        self._reload()
        updated_at = self.trade.updated_at

        self._assert_raises_exact(
            TradeConflict,
            ALREADY_RESOLVED,
            lambda: reject_trade(self.user_b, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.updated_at, updated_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_cancel_on_an_accepted_trade_is_refused(self):
        """Spec 06 case 3: cancelling an accepted trade changes nothing."""
        accept_trade(self.user_b, self.trade)
        self._reload()
        updated_at = self.trade.updated_at

        self._assert_raises_exact(
            TradeConflict,
            ALREADY_RESOLVED,
            lambda: cancel_trade(self.user_a, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.updated_at, updated_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_reject_frees_items_and_a_new_propose_creates_a_second_trade(self):
        """Spec 06 case 4: reject returns both items and allows a new propose."""
        first_id = self.trade.pk

        rejected = reject_trade(self.user_b, self.trade)

        self._reload()
        self.assertEqual(rejected.status, Trade.Status.REJECTED)
        self.assertEqual(self.trade.status, Trade.Status.REJECTED)
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)

        second = propose_trade(self.user_a, self.item_x, self.item_y)

        self._reload()
        self.assertEqual(Trade.objects.count(), 2)
        self.assertEqual(self.trade.pk, first_id)
        self.assertEqual(self.trade.status, Trade.Status.REJECTED)
        self.assertEqual(second.status, Trade.Status.PROPOSED)
        self.assertNotEqual(second.pk, first_id)
        self.assertEqual(second.proposer_id, self.user_a.id)
        self.assertEqual(second.item_offered_id, self.item_x.id)
        self.assertEqual(second.item_requested_id, self.item_y.id)
        self.assertEqual(self.item_x.status, Item.Status.IN_TRADE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)

    def test_cancel_frees_items_and_the_other_owner_can_propose(self):
        """Spec 06 case 5: cancel returns both items and the other owner may propose."""
        first_id = self.trade.pk

        cancelled = cancel_trade(self.user_a, self.trade)

        self._reload()
        self.assertEqual(cancelled.status, Trade.Status.CANCELLED)
        self.assertEqual(self.trade.status, Trade.Status.CANCELLED)
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)

        second = propose_trade(self.user_b, self.item_y, self.item_x)

        self._reload()
        self.assertEqual(Trade.objects.count(), 2)
        self.assertEqual(self.trade.pk, first_id)
        self.assertEqual(self.trade.status, Trade.Status.CANCELLED)
        self.assertEqual(second.proposer_id, self.user_b.id)
        self.assertEqual(second.item_offered_id, self.item_y.id)
        self.assertEqual(second.item_requested_id, self.item_x.id)
        self.assertEqual(second.counterparty_id, self.user_a.id)
        self.assertEqual(second.status, Trade.Status.PROPOSED)
        self.assertEqual(self.item_x.status, Item.Status.IN_TRADE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)

    def test_proposer_cannot_accept(self):
        """Spec 06 case 6: the proposer cannot accept their own proposal."""
        self._assert_raises_exact(
            TradeNotAllowed,
            COUNTERPARTY_ONLY,
            lambda: accept_trade(self.user_a, self.trade),
        )
        self._assert_still_proposed()

    def test_proposer_cannot_reject(self):
        """Spec 06 case 6: the proposer cannot reject their own proposal."""
        self._assert_raises_exact(
            TradeNotAllowed,
            COUNTERPARTY_ONLY,
            lambda: reject_trade(self.user_a, self.trade),
        )
        self._assert_still_proposed()

    def test_counterparty_cannot_cancel(self):
        """Spec 06 case 6: the counterparty cannot cancel."""
        self._assert_raises_exact(
            TradeNotAllowed,
            PROPOSER_ONLY,
            lambda: cancel_trade(self.user_b, self.trade),
        )
        self._assert_still_proposed()

    def test_third_user_cannot_accept(self):
        """Spec 06 case 6: a third user cannot accept a proposed trade."""
        self._assert_raises_exact(
            TradeNotAllowed,
            COUNTERPARTY_ONLY,
            lambda: accept_trade(self.user_c, self.trade),
        )
        self._assert_still_proposed()

    def test_third_user_cannot_reject(self):
        """Spec 06 case 6: a third user cannot reject a proposed trade."""
        self._assert_raises_exact(
            TradeNotAllowed,
            COUNTERPARTY_ONLY,
            lambda: reject_trade(self.user_c, self.trade),
        )
        self._assert_still_proposed()

    def test_third_user_cannot_cancel(self):
        """Spec 06 case 6: a third user cannot cancel a proposed trade."""
        self._assert_raises_exact(
            TradeNotAllowed,
            PROPOSER_ONLY,
            lambda: cancel_trade(self.user_c, self.trade),
        )
        self._assert_still_proposed()

    def test_third_user_accept_on_a_resolved_trade_is_not_allowed(self):
        """Spec 06 case 6: a third user on a resolved trade is refused before state."""
        accept_trade(self.user_b, self.trade)
        self._reload()
        updated_at = self.trade.updated_at

        self._assert_raises_exact(
            TradeNotAllowed,
            COUNTERPARTY_ONLY,
            lambda: accept_trade(self.user_c, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.updated_at, updated_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_third_user_reject_on_a_resolved_trade_is_not_allowed(self):
        """Spec 06 case 6: a third user's reject on a resolved trade is not a conflict."""
        accept_trade(self.user_b, self.trade)
        self._reload()
        updated_at = self.trade.updated_at

        self._assert_raises_exact(
            TradeNotAllowed,
            COUNTERPARTY_ONLY,
            lambda: reject_trade(self.user_c, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.updated_at, updated_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_third_user_cancel_on_a_resolved_trade_is_not_allowed(self):
        """Spec 06 case 6: a third user's cancel on a resolved trade is not a conflict."""
        accept_trade(self.user_b, self.trade)
        self._reload()
        updated_at = self.trade.updated_at

        self._assert_raises_exact(
            TradeNotAllowed,
            PROPOSER_ONLY,
            lambda: cancel_trade(self.user_c, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.trade.updated_at, updated_at)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)

    def test_cancel_after_accept_is_refused_and_items_stay_traded(self):
        """Spec 06 case 8: accept wins, and a later cancel leaves both items traded."""
        accept_trade(self.user_b, self.trade)

        self._assert_raises_exact(
            TradeConflict,
            ALREADY_RESOLVED,
            lambda: cancel_trade(self.user_a, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.ACCEPTED)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(self.item_y.status, Item.Status.TRADED)
        self.assertEqual(Trade.objects.count(), 1)

    def test_accept_after_cancel_is_refused_and_items_stay_available(self):
        """Spec 06 case 8: cancel wins, and a later accept leaves both items available."""
        cancel_trade(self.user_a, self.trade)

        self._assert_raises_exact(
            TradeConflict,
            ALREADY_RESOLVED,
            lambda: accept_trade(self.user_b, self.trade),
        )

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.CANCELLED)
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)
        self.assertEqual(Trade.objects.count(), 1)

    def test_accept_changes_updated_at_without_changing_created_at(self):
        """Spec 06 case 9, resolve half: accept moves updated_at only."""
        created_at = self.trade.created_at
        updated_at = self.trade.updated_at

        accept_trade(self.user_b, self.trade)

        self.trade.refresh_from_db()
        self.assertEqual(self.trade.created_at, created_at)
        self.assertNotEqual(self.trade.updated_at, updated_at)
        self.assertGreater(self.trade.updated_at, created_at)

    def test_reject_changes_updated_at_without_changing_created_at(self):
        """Spec 06 case 9, resolve half: reject moves updated_at only."""
        created_at = self.trade.created_at
        updated_at = self.trade.updated_at

        reject_trade(self.user_b, self.trade)

        self.trade.refresh_from_db()
        self.assertEqual(self.trade.created_at, created_at)
        self.assertNotEqual(self.trade.updated_at, updated_at)
        self.assertGreater(self.trade.updated_at, created_at)

    def test_cancel_changes_updated_at_without_changing_created_at(self):
        """Spec 06 case 9, resolve half: cancel moves updated_at only."""
        created_at = self.trade.created_at
        updated_at = self.trade.updated_at

        cancel_trade(self.user_a, self.trade)

        self.trade.refresh_from_db()
        self.assertEqual(self.trade.created_at, created_at)
        self.assertNotEqual(self.trade.updated_at, updated_at)
        self.assertGreater(self.trade.updated_at, created_at)

    def test_accept_raises_invariant_error_when_offered_item_is_not_in_trade(self):
        """Spec 06 case 14: an out-of-band status rolls the accept back."""
        self.item_x.status = Item.Status.AVAILABLE
        self.item_x.save(update_fields=["status"])

        with self.assertRaises(TradeInvariantError):
            accept_trade(self.user_b, self.trade)

        self._reload()
        self.assertEqual(self.trade.status, Trade.Status.PROPOSED)
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)
        self.assertEqual(self.trade.created_at, self.trade.updated_at)
