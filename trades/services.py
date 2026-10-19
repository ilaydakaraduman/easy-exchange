from django.db import IntegrityError, transaction

from catalog.models import Item

from .models import Like, Match


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
