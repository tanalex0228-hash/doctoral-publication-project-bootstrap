from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from publications.permissions import is_advisor_actor, is_staff_actor


def _post_login_destination(user):
    if is_staff_actor(user):
        return "review:queue"
    if is_advisor_actor(user):
        return "dashboard:advisor"
    return "dashboard:student"


@never_cache
@ensure_csrf_cookie
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_post_login_destination(request.user))
    next_url = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
                return redirect(next_url)
            return redirect(_post_login_destination(form.get_user()))
    else:
        form = AuthenticationForm(request)
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@login_required
def home_view(request):
    return redirect(_post_login_destination(request.user))
