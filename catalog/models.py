from django.conf import settings
from django.db import models


class Category(models.Model):
    slug = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=80)
    metadata_schema = models.JSONField()

    def __str__(self):
        return self.slug


class Item(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "AVAILABLE"
        IN_TRADE = "IN_TRADE", "IN_TRADE"
        TRADED = "TRADED", "TRADED"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="items",
    )
    title = models.CharField(max_length=120)
    description = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
