from django.db.models import Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Item

from .models import Match, Trade
from .services import (
    LikeNotAllowed,
    TradeConflict,
    TradeNotAllowed,
    accept_trade,
    cancel_trade,
    like_item,
    propose_trade,
    reject_trade,
)


def like(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect("/login")

    item = get_object_or_404(Item, pk=item_id)
    if request.user.pk == item.owner_id:
        return _plain(403, "You cannot like your own listing.")
    try:
        like_item(request.user, item)
    except LikeNotAllowed as exc:
        return _plain(403, str(exc))
    return redirect(f"/listings/{item.pk}")


def matches(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if not request.user.is_authenticated:
        return redirect("/login?next=/matches")

    user = request.user
    rows = (
        Match.objects.filter(Q(item_a__owner=user) | Q(item_b__owner=user))
        .select_related(
            "item_a__owner",
            "item_a__category",
            "item_b__owner",
            "item_b__category",
        )
        .order_by("id")
    )
    pairs = [_pair_for(user, match) for match in rows]
    incoming, outgoing, finished = _trade_sections(user)
    return render(
        request,
        "trades/matches.html",
        {
            "pairs": pairs,
            "incoming": incoming,
            "outgoing": outgoing,
            "finished": finished,
        },
    )


def propose(request, match_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect("/login")

    match = get_object_or_404(
        Match.objects.select_related("item_a", "item_b"),
        pk=match_id,
    )
    if match.item_a.owner_id == request.user.pk:
        item_offered, item_requested = match.item_a, match.item_b
    elif match.item_b.owner_id == request.user.pk:
        item_offered, item_requested = match.item_b, match.item_a
    else:
        return _plain(403, "You are not part of this match.")
    return _call_trade(propose_trade, request.user, item_offered, item_requested)


def accept(request, trade_id):
    return _resolve_view(request, trade_id, accept_trade)


def reject(request, trade_id):
    return _resolve_view(request, trade_id, reject_trade)


def cancel(request, trade_id):
    return _resolve_view(request, trade_id, cancel_trade)


def _resolve_view(request, trade_id, service):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect("/login")
    trade = get_object_or_404(Trade, pk=trade_id)
    return _call_trade(service, request.user, trade)


def _call_trade(service, *args):
    try:
        service(*args)
    except TradeNotAllowed as exc:
        return _plain(403, str(exc))
    except TradeConflict as exc:
        return _plain(409, str(exc))
    return redirect("/matches")


def _trade_sections(user):
    trades = Trade.objects.filter(Q(proposer=user) | Q(counterparty=user)).select_related(
        "item_offered__owner",
        "item_requested__owner",
        "proposer",
        "counterparty",
    )
    incoming = []
    outgoing = []
    finished = []
    terminal = (
        Trade.Status.ACCEPTED,
        Trade.Status.REJECTED,
        Trade.Status.CANCELLED,
    )
    for trade in trades:
        row = _trade_row(user, trade)
        if trade.status == Trade.Status.PROPOSED and trade.counterparty_id == user.pk:
            incoming.append(row)
        elif trade.status == Trade.Status.PROPOSED and trade.proposer_id == user.pk:
            outgoing.append(row)
        elif trade.status in terminal:
            finished.append(row)
    incoming.sort(key=lambda row: (row["trade"].created_at, row["trade"].id))
    outgoing.sort(key=lambda row: (row["trade"].created_at, row["trade"].id))
    finished.sort(
        key=lambda row: (row["trade"].updated_at, row["trade"].id),
        reverse=True,
    )
    return incoming, outgoing, finished


def _trade_row(user, trade):
    if trade.item_offered.owner_id == user.pk:
        your_item = trade.item_offered
        their_item = trade.item_requested
    else:
        your_item = trade.item_requested
        their_item = trade.item_offered
    if trade.proposer_id == user.pk:
        proposed_by = "You"
        other_name = trade.counterparty.display_name
    else:
        proposed_by = trade.proposer.display_name
        other_name = trade.proposer.display_name
    return {
        "trade": trade,
        "your_item": your_item,
        "their_item": their_item,
        "other_name": other_name,
        "proposed_by": proposed_by,
    }


def _pair_for(user, match):
    if match.item_a.owner_id == user.pk:
        your_item = match.item_a
        their_item = match.item_b
    else:
        your_item = match.item_b
        their_item = match.item_a
    return {
        "match": match,
        "your_item": your_item,
        "their_item": their_item,
        "other_owner_name": their_item.owner.display_name,
    }


def _plain(status, message):
    return HttpResponse(message, status=status, content_type="text/plain; charset=utf-8")
