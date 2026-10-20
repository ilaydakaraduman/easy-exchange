from urllib.parse import urlencode

from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from trades.models import Like, Match

from .forms import ListingForm, initial_from_item
from .models import Category, Item


def browse(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    categories = list(Category.objects.order_by("slug"))
    raw = request.GET.get("category") if "category" in request.GET else None
    active_category = None
    if raw not in (None, "", "all"):
        active_category = next(
            (category for category in categories if category.slug == raw),
            None,
        )
        if active_category is None:
            raise Http404

    game_choices = _tcg_game_choices(categories)
    raw_game = request.GET.get("game") if "game" in request.GET else None
    active_game = None
    if raw_game not in (None, "", "all"):
        if raw_game not in game_choices:
            raise Http404
        if active_category is not None and active_category.slug == "tcg":
            active_game = raw_game

    q = request.GET.get("q", "")
    q = "" if q is None else q.strip()[:100]

    items = Item.objects.select_related("owner", "category").order_by(
        "-created_at",
        "-id",
    )
    if active_category is not None:
        items = items.filter(category=active_category)
    if active_game:
        items = items.filter(metadata__game=active_game)
    if q:
        items = items.filter(Q(title__icontains=q) | Q(description__icontains=q))

    game_links = []
    if active_category is not None and active_category.slug == "tcg" and game_choices:
        game_links.append(
            {
                "text": "All games",
                "href": _game_href(q, None),
                "current": active_game is None,
            }
        )
        for choice in game_choices:
            game_links.append(
                {
                    "text": choice,
                    "href": _game_href(q, choice),
                    "current": active_game == choice,
                }
            )

    return render(
        request,
        "catalog/browse.html",
        {
            "categories": categories,
            "active_category": active_category,
            "active_game": active_game,
            "game_links": game_links,
            "items": items,
            "q": q,
        },
    )


def _tcg_game_choices(categories):
    for category in categories:
        if category.slug != "tcg":
            continue
        for entry in category.metadata_schema or []:
            if entry.get("key") == "game":
                return list(entry.get("choices") or [])
    return []


def _game_href(q, game):
    params = {"category": "tcg"}
    if game is not None:
        params["game"] = game
    if q:
        params["q"] = q
    return "/?" + urlencode(params)


def listing_detail(request, item_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    item = get_object_or_404(
        Item.objects.select_related("owner", "category"),
        pk=item_id,
    )
    viewer_has_liked = False
    has_match_with_viewer = False
    if request.user.is_authenticated:
        viewer_has_liked = Like.objects.filter(user=request.user, item=item).exists()
        has_match_with_viewer = Match.objects.filter(
            Q(item_a=item, item_b__owner=request.user)
            | Q(item_b=item, item_a__owner=request.user)
        ).exists()
    return render(
        request,
        "catalog/item_detail.html",
        {
            "item": item,
            "viewer_has_liked": viewer_has_liked,
            "has_match_with_viewer": has_match_with_viewer,
        },
    )


def listing_create(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not request.user.is_authenticated:
        if request.method == "GET":
            return redirect("/login?next=/listings/new")
        return redirect("/login")

    categories = Category.objects.order_by("slug")
    if request.method == "GET":
        if "category" not in request.GET:
            return render(
                request,
                "catalog/listing_form.html",
                {
                    "categories": categories,
                    "selected_category": None,
                    "form": None,
                },
            )
        category = get_object_or_404(Category, slug=request.GET.get("category", ""))
        form = ListingForm(category=category)
        return render(
            request,
            "catalog/listing_form.html",
            {
                "categories": categories,
                "selected_category": category,
                "form": form,
            },
        )

    category = get_object_or_404(Category, slug=request.POST.get("category", ""))
    form = ListingForm(request.POST, request.FILES, category=category)
    if form.is_valid():
        item = Item.objects.create(
            owner=request.user,
            category=category,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            metadata=form.cleaned_metadata,
            photo=form.cleaned_data.get("photo") or "",
        )
        return redirect(f"/listings/{item.pk}")
    return render(
        request,
        "catalog/listing_form.html",
        {
            "categories": categories,
            "selected_category": category,
            "form": form,
        },
    )


def listing_edit(request, item_id):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not request.user.is_authenticated:
        if request.method == "GET":
            return redirect(f"/login?next=/listings/{item_id}/edit")
        return redirect("/login")

    item = get_object_or_404(
        Item.objects.select_related("owner", "category"),
        pk=item_id,
    )
    if item.owner_id != request.user.pk:
        return _forbidden("You can only edit your own listings.")
    if item.status != Item.Status.AVAILABLE:
        return _forbidden("This listing is in a trade and cannot be edited.")

    if request.method == "GET":
        form = ListingForm(
            category=item.category,
            initial=initial_from_item(item),
        )
    else:
        form = ListingForm(request.POST, request.FILES, category=item.category)
        if form.is_valid():
            updated = Item.objects.filter(
                pk=item.pk,
                owner=request.user,
                status=Item.Status.AVAILABLE,
            ).update(
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                metadata=form.cleaned_metadata,
            )
            if updated == 0:
                return _forbidden("This listing is in a trade and cannot be edited.")
            photo = form.cleaned_data.get("photo")
            if photo:
                item.photo = photo
                item.save(update_fields=["photo"])
            return redirect(f"/listings/{item.pk}")

    return render(
        request,
        "catalog/listing_edit.html",
        {
            "item": item,
            "category_name": item.category.name,
            "form": form,
        },
    )


def _forbidden(message):
    return HttpResponse(message, status=403, content_type="text/plain; charset=utf-8")
