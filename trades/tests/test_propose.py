from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Trade
from trades.services import (
    TradeConflict,
    TradeNotAllowed,
    like_item,
    propose_trade,
)

User = get_user_model()

LOCK_REFUSED = "One of these listings is no longer available."


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
class ProposeTradeTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=[],
        )
        self.user_a = make_user("a@example.com", "User A")
        self.user_b = make_user("b@example.com", "User B")
        self.user_c = make_user("c@example.com", "User C")
        self.user_d = make_user("d@example.com", "User D")
        self.item_x = make_item(self.user_a, self.category, "Item X")
        self.item_y = make_item(self.user_b, self.category, "Item Y")
        self.item_z = make_item(self.user_c, self.category, "Item Z")
        self.item_w = make_item(self.user_d, self.category, "Item W")

    def _assert_raises_exact(self, exc_class, message, func):
        with self.assertRaises(exc_class) as raised:
            func()
        self.assertEqual(str(raised.exception), message)

    def _assert_no_trade_and_available(self, *items):
        for item in items:
            item.refresh_from_db()
            self.assertEqual(item.status, Item.Status.AVAILABLE)
        self.assertEqual(Trade.objects.count(), 0)

    def _assert_lock_still_held(self, trade, *still_available):
        trade.refresh_from_db()
        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        for item in still_available:
            item.refresh_from_db()
            self.assertEqual(item.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_x.status, Item.Status.IN_TRADE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)
        self.assertEqual(trade.status, Trade.Status.PROPOSED)
        self.assertEqual(Trade.objects.count(), 1)

    def test_propose_locks_both_items_and_creates_one_proposed_trade(self):
        """Spec 06 case 1: a propose on two available matched items locks both."""
        match_items(self.item_x, self.item_y)

        trade = propose_trade(self.user_a, self.item_x, self.item_y)

        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        stored = Trade.objects.get()
        self.assertEqual(self.item_x.status, Item.Status.IN_TRADE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)
        self.assertEqual(stored.pk, trade.pk)
        self.assertEqual(stored.item_offered_id, self.item_x.id)
        self.assertEqual(stored.item_requested_id, self.item_y.id)
        self.assertEqual(stored.proposer_id, self.user_a.id)
        self.assertEqual(stored.counterparty_id, self.user_b.id)
        self.assertEqual(stored.status, Trade.Status.PROPOSED)
        self.assertEqual(stored.created_at, stored.updated_at)
        self.assertEqual(Trade.objects.count(), 1)

    def test_either_owner_may_propose(self):
        """Spec 06 case 2: the other matched owner can propose their own item."""
        match_items(self.item_x, self.item_y)

        trade = propose_trade(self.user_b, self.item_y, self.item_x)

        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        self.assertEqual(trade.item_offered_id, self.item_y.id)
        self.assertEqual(trade.item_requested_id, self.item_x.id)
        self.assertEqual(trade.proposer_id, self.user_b.id)
        self.assertEqual(trade.counterparty_id, self.user_a.id)
        self.assertEqual(trade.status, Trade.Status.PROPOSED)
        self.assertEqual(self.item_x.status, Item.Status.IN_TRADE)
        self.assertEqual(self.item_y.status, Item.Status.IN_TRADE)
        self.assertEqual(Trade.objects.count(), 1)

    def test_propose_refused_when_user_does_not_own_the_offered_item(self):
        """Spec 06 case 7a: only the owner of item_offered may propose it."""
        self._assert_raises_exact(
            TradeNotAllowed,
            "You can only offer your own listing.",
            lambda: propose_trade(self.user_b, self.item_x, self.item_y),
        )
        self._assert_no_trade_and_available(
            self.item_x, self.item_y, self.item_z, self.item_w
        )

    def test_propose_refused_when_both_items_belong_to_the_same_owner(self):
        """Spec 06 case 7b: two listings owned by the same user cannot be traded."""
        item_x2 = make_item(self.user_a, self.category, "Item X2")

        self._assert_raises_exact(
            TradeNotAllowed,
            "You cannot trade with yourself.",
            lambda: propose_trade(self.user_a, self.item_x, item_x2),
        )
        self._assert_no_trade_and_available(
            self.item_x, item_x2, self.item_y, self.item_z, self.item_w
        )

    def test_propose_refused_when_offering_an_item_for_itself(self):
        """Spec 06 case 7b: an item cannot be offered for itself."""
        self._assert_raises_exact(
            TradeNotAllowed,
            "You cannot trade with yourself.",
            lambda: propose_trade(self.user_a, self.item_x, self.item_x),
        )
        self._assert_no_trade_and_available(
            self.item_x, self.item_y, self.item_z, self.item_w
        )

    def test_propose_refused_when_listings_are_not_matched(self):
        """Spec 06 case 7c: a pair with no Match cannot be proposed."""
        self._assert_raises_exact(
            TradeNotAllowed,
            "These listings are not matched.",
            lambda: propose_trade(self.user_a, self.item_x, self.item_z),
        )
        self._assert_no_trade_and_available(
            self.item_x, self.item_y, self.item_z, self.item_w
        )

    def test_propose_sets_created_at_equal_to_updated_at(self):
        """Spec 06 case 9, create half: a new trade's timestamps match."""
        match_items(self.item_x, self.item_y)

        trade = propose_trade(self.user_a, self.item_x, self.item_y)

        trade.refresh_from_db()
        self.assertIsNotNone(trade.created_at)
        self.assertEqual(trade.created_at, trade.updated_at)

    def test_second_propose_on_a_locked_item_is_refused(self):
        """Spec 06 case 10: a locked item cannot enter a second live trade."""
        match_items(self.item_x, self.item_y)
        match_items(self.item_x, self.item_z)
        trade = propose_trade(self.user_a, self.item_x, self.item_y)

        self._assert_raises_exact(
            TradeConflict,
            LOCK_REFUSED,
            lambda: propose_trade(self.user_c, self.item_z, self.item_x),
        )
        self._assert_lock_still_held(trade, self.item_z)

        self._assert_raises_exact(
            TradeConflict,
            LOCK_REFUSED,
            lambda: propose_trade(self.user_a, self.item_x, self.item_z),
        )
        self._assert_lock_still_held(trade, self.item_z)

    def test_second_propose_on_a_locked_requested_item_is_refused(self):
        """Spec 06 case 11: item_requested of a live trade is locked too."""
        match_items(self.item_x, self.item_y)
        match_items(self.item_y, self.item_w)
        trade = propose_trade(self.user_a, self.item_x, self.item_y)

        self._assert_raises_exact(
            TradeConflict,
            LOCK_REFUSED,
            lambda: propose_trade(self.user_d, self.item_w, self.item_y),
        )
        self._assert_lock_still_held(trade, self.item_w)

    def test_propose_rolls_back_when_one_item_is_already_traded(self):
        """Spec 06 case 12: a TRADED item refuses the propose and rolls back."""
        match_items(self.item_x, self.item_z)
        self.item_x.status = Item.Status.TRADED
        self.item_x.save(update_fields=["status"])

        self._assert_raises_exact(
            TradeConflict,
            LOCK_REFUSED,
            lambda: propose_trade(self.user_c, self.item_z, self.item_x),
        )

        self.item_x.refresh_from_db()
        self.item_z.refresh_from_db()
        self.assertEqual(self.item_z.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_x.status, Item.Status.TRADED)
        self.assertEqual(Trade.objects.count(), 0)

    def test_propose_rolls_back_when_trade_creation_fails(self):
        """Spec 06 case 13: a failed Trade insert rolls back both item locks."""
        match_items(self.item_x, self.item_y)

        with patch(
            "trades.services.Trade.objects.create",
            side_effect=RuntimeError("insert failed"),
        ):
            with self.assertRaises(RuntimeError) as raised:
                propose_trade(self.user_a, self.item_x, self.item_y)

        self.assertEqual(str(raised.exception), "insert failed")
        self.item_x.refresh_from_db()
        self.item_y.refresh_from_db()
        self.assertEqual(self.item_x.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)
        self.assertEqual(Trade.objects.count(), 0)
