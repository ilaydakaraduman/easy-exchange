from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, RegistrationForm

User = get_user_model()


def safe_redirect_url(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return "/"


def register(request):
    if request.method == "GET" and request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            User.objects.create_user(
                email=form.cleaned_data["email"],
                display_name=form.cleaned_data["display_name"],
                password=form.cleaned_data["password"],
            )
            return redirect("/login")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.method == "GET" and request.user.is_authenticated:
        return redirect("/")
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            if user is None:
                form.add_error(None, "Invalid email or password.")
            else:
                login(request, user)
                return redirect(safe_redirect_url(request, next_url))
    else:
        form = LoginForm()
    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": next_url},
    )


def logout_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    logout(request)
    return redirect("/")
