from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from publications.permissions import is_staff_actor
from doctoral_students.models import DoctoralStudentProfile
from publications.models import PublicationRecord
from publications.querysets import official_publications
from audit.services import record_event
from .forms import SupportEmailForm
from .models import SiteConfiguration


def _post_login_destination(user):
    if is_staff_actor(user):
        return "review:queue"
    if user.has_project_role("student") and DoctoralStudentProfile.objects.filter(user=user).exists():
        return "dashboard:student"
    return "accounts:profile"


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


@login_required
@never_cache
def profile_view(request):
    try:
        student = request.user.doctoral_profile
    except DoctoralStudentProfile.DoesNotExist:
        student = None
    publications = PublicationRecord.objects.none()
    approved = PublicationRecord.objects.none()
    if student:
        publications = PublicationRecord.objects.filter(
            owner_student=student, is_revision=False, is_trashed=False, is_purged=False,
        ).select_related("publication_type").order_by("-updated_at")
        approved = official_publications().filter(owner_student=student).select_related("publication_type")
    return render(request, "accounts/profile.html", {
        "student": student,
        "drafts": publications.filter(workflow_status=PublicationRecord.WorkflowStatus.DRAFT),
        "submitted": publications.filter(workflow_status=PublicationRecord.WorkflowStatus.SUBMITTED),
        "returned": publications.filter(workflow_status=PublicationRecord.WorkflowStatus.RETURNED),
        "approved": approved,
        "home_destination": _post_login_destination(request.user),
    })


@login_required
@never_cache
def password_change_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "密碼已更新。")
        return redirect("accounts:profile")
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
@require_POST
def update_support_email(request):
    """Only the explicit Django root may change the footer contact address."""
    if not request.user.is_superuser:
        raise Http404("Resource not found.")
    form = SupportEmailForm(request.POST)
    if form.is_valid():
        configuration, _ = SiteConfiguration.objects.update_or_create(
            pk=1,
            defaults={"support_email": form.cleaned_data["support_email"], "updated_by": request.user},
        )
        record_event(actor=request.user, action="site_configuration.support_email_updated", target=configuration)
        messages.success(request, "頁尾聯絡信箱已更新。")
    else:
        messages.error(request, "請輸入有效的聯絡信箱。")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return redirect(next_url)
    return redirect("accounts:home")
