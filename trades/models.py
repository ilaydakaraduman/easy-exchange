from django.conf import settings
from django.db import models


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.CASCADE,
        related_name="likes",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"],
                name="like_unique_user_item",
            ),
        ]


class Match(models.Model):
    item_a = models.ForeignKey(
        "catalog.Item",
        on_delete=models.CASCADE,
        related_name="matches_as_a",
    )
    item_b = models.ForeignKey(
        "catalog.Item",
        on_delete=models.CASCADE,
        related_name="matches_as_b",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item_a", "item_b"],
                name="match_unique_item_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(item_a_id__lt=models.F("item_b_id")),
                name="match_item_a_id_lt_item_b_id",
            ),
        ]
