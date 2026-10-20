from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import Item

from .models import Like, Match, Trade


class LikeNotAllowed(Exception):
    pass


def like_item(user, item):
    """Create a like and any reciprocal matches. The only creation path."""
    with transaction.atomic():
        if user.pk == item.owner_id:
            raise LikeNotAllowed("You cannot like your own listing.")
        if item.status == Item.Status.TRADED:
            raise LikeNotAllowed("This listing has already been traded.")

        like, _created = Like.objects.get_or_create(user=user, item=item)
        created_matches = []
        reciprocal = Like.objects.filter(
            user_id=item.owner_id,
            item__owner_id=user.pk,
        ).select_related("item")
        for other_like in reciprocal:
            match = _match_for_pair(other_like.item, item)
            if match is not None:
                created_matches.append(match)
        return like, created_matches


def _match_for_pair(item_x, item_y):
    if item_x.pk == item_y.pk:
        return None
    if item_x.pk < item_y.pk:
        item_a, item_b = item_x, item_y
    else:
        item_a, item_b = item_y, item_x
    match, was_created = _get_or_create_match(item_a, item_b)
    if was_created:
        return match
    return None


class TradeNotAllowed(Exception):
    pass


class TradeConflict(Exception):
    pass


class TradeInvariantError(Exception):
    pass


def propose_trade(user, item_offered, item_requested):
    """Lock both items and create one PROPOSED trade. The only creation path."""
    if _actor_id(user) != item_offered.owner_id:
        raise TradeNotAllowed("You can only offer your own listing.")
    if (
        item_offered.id == item_requested.id
        or item_offered.owner_id == item_requested.owner_id
    ):
        raise TradeNotAllowed("You cannot trade with yourself.")
    low_id, high_id = sorted((item_offered.id, item_requested.id))
    if not Match.objects.filter(item_a_id=low_id, item_b_id=high_id).exists():
        raise TradeNotAllowed("These listings are not matched.")

    with transaction.atomic():
        updated = Item.objects.filter(
            id__in=[item_offered.id, item_requested.id],
            status=Item.Status.AVAILABLE,
        ).update(status=Item.Status.IN_TRADE)
        if updated != 2:
            raise TradeConflict("One of these listings is no longer available.")
        now = timezone.now()
        trade = Trade.objects.create(
            item_offered=item_offered,
            item_requested=item_requested,
            proposer=user,
            counterparty_id=item_requested.owner_id,
            status=Trade.Status.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        item_offered.refresh_from_db(fields=["status"])
        item_requested.refresh_from_db(fields=["status"])
        return trade


def accept_trade(user, trade):
    _require_counterparty(user, trade)
    return _resolve(trade, Trade.Status.ACCEPTED, Item.Status.TRADED)


def reject_trade(user, trade):
    _require_counterparty(user, trade)
    return _resolve(trade, Trade.Status.REJECTED, Item.Status.AVAILABLE)


def cancel_trade(user, trade):
    if _actor_id(user) != trade.proposer_id:
        raise TradeNotAllowed("Only the proposer can cancel this trade.")
    return _resolve(trade, Trade.Status.CANCELLED, Item.Status.AVAILABLE)


def _require_counterparty(user, trade):
    if _actor_id(user) != trade.counterparty_id:
        raise TradeNotAllowed("Only the counterparty can accept or reject this trade.")


def _resolve(trade, new_status, item_status):
    with transaction.atomic():
        now = timezone.now()
        if trade.created_at is not None and now <= trade.created_at:
            now = trade.created_at + timedelta(microseconds=1)
        updated = Trade.objects.filter(
            id=trade.id,
            status=Trade.Status.PROPOSED,
        ).update(status=new_status, updated_at=now)
        if updated != 1:
            raise TradeConflict("This trade has already been resolved.")
        item_rows = Item.objects.filter(
            id__in=[trade.item_offered_id, trade.item_requested_id],
            status=Item.Status.IN_TRADE,
        ).update(status=item_status)
        if item_rows != 2:
            raise TradeInvariantError(
                "Both items of a PROPOSED trade must be IN_TRADE."
            )
        trade.refresh_from_db()
        return trade


def _actor_id(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user.pk


def _get_or_create_match(item_a, item_b):
    try:
        return Match.objects.get(item_a=item_a, item_b=item_b), False
    except Match.DoesNotExist:
        pass
    try:
        with transaction.atomic():
            return Match.objects.create(item_a=item_a, item_b=item_b), True
    except IntegrityError:
        return Match.objects.get(item_a=item_a, item_b=item_b), False
