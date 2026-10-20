from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Like, Match
from trades.services import LikeNotAllowed, like_item
from trades.tests.test_propose import make_item, make_user

OWN_ITEM = "You cannot like your own listing."
ALREADY_TRADED = "This listing has already been traded."


def _pair_key(left, right):
    low, high = sorted((left.id, right.id))
    return (low, high)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class LikeItemTests(TestCase):
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

    def _assert_ordered(self, match, left, right):
        self.assertEqual(match.item_a_id, min(left.id, right.id))
        self.assertEqual(match.item_b_id, max(left.id, right.id))

    def test_own_item_is_refused(self):
        """Spec 05 case 1: a user cannot like their own listing."""
        with self.assertRaises(LikeNotAllowed) as raised:
            like_item(self.user_a, self.item_x)

        self.assertEqual(str(raised.exception), OWN_ITEM)
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(Match.objects.count(), 0)

    def test_single_like_creates_no_match(self):
        """Spec 05 case 2: one like with no reciprocal like creates no match."""
        like, created = like_item(self.user_a, self.item_y)

        self.assertEqual(created, [])
        self.assertEqual(like.user_id, self.user_a.id)
        self.assertEqual(like.item_id, self.item_y.id)
        self.assertEqual(Like.objects.filter(user=self.user_a, item=self.item_y).count(), 1)
        self.assertEqual(Match.objects.count(), 0)

    def test_duplicate_like_is_idempotent(self):
        """Spec 05 case 3: liking the same item twice keeps a single like."""
        _, first = like_item(self.user_a, self.item_y)
        _, second = like_item(self.user_a, self.item_y)

        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertEqual(
            Like.objects.filter(user=self.user_a, item=self.item_y).count(),
            1,
        )
        self.assertEqual(Match.objects.count(), 0)

    def test_reciprocal_like_creates_one_match_ordered_by_id(self):
        """Spec 05 case 4: a reciprocal like creates one match ordered by item id."""
        self.assertLess(self.item_x.id, self.item_y.id)

        _, first = like_item(self.user_b, self.item_x)
        _, created = like_item(self.user_a, self.item_y)

        self.assertEqual(first, [])
        self.assertEqual(len(created), 1)
        self._assert_ordered(created[0], self.item_x, self.item_y)
        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(Match.objects.get().pk, created[0].pk)

    def test_reciprocal_like_orders_match_when_the_liked_item_has_the_smaller_id(self):
        """Spec 05 case 4: ordering still holds when the second item was created first."""
        item_y = make_item(self.user_b, self.category, "Item Y first")
        item_x = make_item(self.user_a, self.category, "Item X second")
        self.assertLess(item_y.id, item_x.id)

        _, first = like_item(self.user_b, item_x)
        _, created = like_item(self.user_a, item_y)

        self.assertEqual(first, [])
        self.assertEqual(len(created), 1)
        self._assert_ordered(created[0], item_x, item_y)
        self.assertEqual(Match.objects.count(), 1)

    def test_order_of_likes_does_not_matter(self):
        """Spec 05 case 5: the match is the same when the other owner likes first."""
        _, first = like_item(self.user_a, self.item_y)
        _, created = like_item(self.user_b, self.item_x)

        self.assertEqual(first, [])
        self.assertEqual(len(created), 1)
        self._assert_ordered(created[0], self.item_x, self.item_y)
        self.assertEqual(Match.objects.count(), 1)

    def test_repeated_reciprocal_pair_creates_no_second_match(self):
        """Spec 05 case 6: liking a completed pair again does not create another match."""
        like_item(self.user_b, self.item_x)
        like_item(self.user_a, self.item_y)

        _, again_a = like_item(self.user_a, self.item_y)
        _, again_b = like_item(self.user_b, self.item_x)

        self.assertEqual(again_a, [])
        self.assertEqual(again_b, [])
        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(Like.objects.count(), 2)

    def test_one_like_completes_several_pairs(self):
        """Spec 05 case 7: one like creates a match for every item the other owner liked."""
        item_x2 = make_item(self.user_a, self.category, "Item X2")
        like_item(self.user_b, self.item_x)
        like_item(self.user_b, item_x2)

        _, created = like_item(self.user_a, self.item_y)

        self.assertEqual(
            {_pair_key(match.item_a, match.item_b) for match in created},
            {_pair_key(self.item_x, self.item_y), _pair_key(item_x2, self.item_y)},
        )
        for match in created:
            self.assertLess(match.item_a_id, match.item_b_id)
        self.assertEqual(Match.objects.count(), 2)

    def test_existing_matches_stay_when_more_pairs_complete(self):
        """Spec 05 case 8: a later like adds matches and leaves existing rows unchanged."""
        item_x2 = make_item(self.user_a, self.category, "Item X2")
        like_item(self.user_b, self.item_x)
        like_item(self.user_b, item_x2)
        like_item(self.user_a, self.item_y)
        original = list(
            Match.objects.order_by("id").values_list("id", "item_a_id", "item_b_id")
        )
        item_y2 = make_item(self.user_b, self.category, "Item Y2")

        _, created = like_item(self.user_a, item_y2)

        self.assertEqual(Match.objects.count(), 4)
        self.assertEqual(
            list(
                Match.objects.filter(id__in=[row[0] for row in original])
                .order_by("id")
                .values_list("id", "item_a_id", "item_b_id")
            ),
            original,
        )
        self.assertEqual(
            {_pair_key(match.item_a, match.item_b) for match in created},
            {_pair_key(self.item_x, item_y2), _pair_key(item_x2, item_y2)},
        )
        self.assertTrue({match.id for match in created}.isdisjoint(row[0] for row in original))

    def test_no_cross_user_matches(self):
        """Spec 05 case 9: a match is only created for the two owners who liked each other."""
        item_c = make_item(self.user_c, self.category, "Item C")
        like_item(self.user_a, self.item_y)
        like_item(self.user_c, self.item_y)

        _, created = like_item(self.user_b, self.item_x)

        self.assertEqual(len(created), 1)
        self._assert_ordered(created[0], self.item_x, self.item_y)
        self.assertEqual(Match.objects.count(), 1)
        for match in Match.objects.all():
            self.assertNotIn(item_c.id, (match.item_a_id, match.item_b_id))

    def test_unique_and_check_constraints_reject_direct_inserts(self):
        """Spec 05 case 10: the pair unique constraint and id order check reject bad rows."""
        like_item(self.user_b, self.item_x)
        like_item(self.user_a, self.item_y)
        match = Match.objects.get()
        low = Item.objects.get(pk=match.item_a_id)
        high = Item.objects.get(pk=match.item_b_id)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Match.objects.create(item_a=low, item_b=high)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Match.objects.create(item_a=high, item_b=low)

        self.assertEqual(Match.objects.count(), 1)

    def test_like_rolls_back_when_match_creation_fails(self):
        """Spec 05 case 11: a failed match insert rolls back the like written in that call."""
        like_item(self.user_b, self.item_x)

        with patch(
            "trades.services.Match.objects.create",
            side_effect=RuntimeError("match failed"),
        ):
            with self.assertRaises(RuntimeError) as raised:
                like_item(self.user_a, self.item_y)

        self.assertEqual(str(raised.exception), "match failed")
        self.assertFalse(Like.objects.filter(user=self.user_a, item=self.item_y).exists())
        self.assertEqual(Like.objects.filter(user=self.user_b, item=self.item_x).count(), 1)
        self.assertEqual(Match.objects.count(), 0)

    def test_in_trade_item_may_be_liked(self):
        """Spec 05 case 12: an IN_TRADE item can be liked and can complete a match."""
        like_item(self.user_b, self.item_x)
        self.item_y.status = Item.Status.IN_TRADE
        self.item_y.save(update_fields=["status"])

        _, created = like_item(self.user_a, self.item_y)

        self.assertEqual(len(created), 1)
        self._assert_ordered(created[0], self.item_x, self.item_y)
        self.assertEqual(Like.objects.filter(user=self.user_a, item=self.item_y).count(), 1)
        self.assertEqual(Match.objects.count(), 1)

    def test_traded_item_is_refused(self):
        """Spec 05 case 13: a TRADED item cannot be liked."""
        like_item(self.user_b, self.item_x)
        self.item_y.status = Item.Status.TRADED
        self.item_y.save(update_fields=["status"])

        with self.assertRaises(LikeNotAllowed) as raised:
            like_item(self.user_a, self.item_y)

        self.assertEqual(str(raised.exception), ALREADY_TRADED)
        self.assertFalse(Like.objects.filter(user=self.user_a, item=self.item_y).exists())
        self.assertEqual(Match.objects.count(), 0)

    def test_callers_own_traded_item_can_still_complete_a_match(self):
        """Spec 05 case 13: only the liked item's status is checked."""
        like_item(self.user_b, self.item_x)
        self.item_x.status = Item.Status.TRADED
        self.item_x.save(update_fields=["status"])

        _, created = like_item(self.user_a, self.item_y)

        self.assertEqual(len(created), 1)
        self._assert_ordered(created[0], self.item_x, self.item_y)
        self.assertEqual(Like.objects.filter(user=self.user_a, item=self.item_y).count(), 1)
        self.item_y.refresh_from_db()
        self.assertEqual(self.item_y.status, Item.Status.AVAILABLE)
