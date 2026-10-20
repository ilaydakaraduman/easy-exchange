from django.urls import path

from . import views

urlpatterns = [
    path("listings/<int:item_id>/like", views.like, name="like"),
    path("matches", views.matches, name="matches"),
    path("matches/<int:match_id>/propose", views.propose, name="propose"),
    path("trades/<int:trade_id>/accept", views.accept, name="accept"),
    path("trades/<int:trade_id>/reject", views.reject, name="reject"),
    path("trades/<int:trade_id>/cancel", views.cancel, name="cancel"),
]
