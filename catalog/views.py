from django.db.models import Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from trades.models import Like, Match

from .forms import ListingForm, initial_from_item
from .models import Category, Item


def browse(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    categories = Category.objects.order_by("slug")
    raw = request.GET.get("category") if "category" in request.GET else None
    active_category = None
    if raw not in (None, "", "all"):
        active_category = get_object_or_404(Category, slug=raw)

    items = Item.objects.select_related("owner", "category").order_by(
        "-created_at",
        "-id",
    )
    if active_category is not None:
        items = items.filter(category=active_category)

    return render(
        request,
        "catalog/browse.html",
        {
            "categories": categories,
            "active_category": active_category,
            "items": items,
        },
    )


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
    form = ListingForm(request.POST, category=category)
    if form.is_valid():
        item = Item.objects.create(
            owner=request.user,
            category=category,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            metadata=form.cleaned_metadata,
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
        form = ListingForm(request.POST, category=item.category)
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
