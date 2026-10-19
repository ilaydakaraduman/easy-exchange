from django.urls import path

from . import views

urlpatterns = [
    path("listings/new", views.listing_create, name="listing_create"),
    path("listings/<int:item_id>/edit", views.listing_edit, name="listing_edit"),
    path("listings/<int:item_id>", views.listing_detail, name="listing_detail"),
]
