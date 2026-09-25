from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from config.pagination import paginate_queryset
from publications.models import PublicationRecord
from publications.permissions import is_staff_actor
from publications.querysets import is_official_publication, official_publications
from publications.services import set_published, set_visibility
from taxonomy.models import PublicationType
from .forms import PublicationSettingsForm, ReturnForRevisionForm, RevokeApprovalForm
from .models import PublicationTransition
from .services import approve_publication, archive_publication, return_for_revision, revoke_approval


def _require_review_role(request):
    if not is_staff_actor(request.user):
        raise Http404("Review resource not found.")


def _review_queryset():
    return PublicationRecord.objects.select_related("owner_student", "publication_type").prefetch_related(
        "owner_student__advisor_relations__professor", "authors", "indices", "research_fields", "documents",
        "review_decisions", "transitions",
    )


@login_required
def review_queue(request):
    _require_review_role(request)
    publications = _review_queryset().filter(workflow_status=PublicationRecord.WorkflowStatus.SUBMITTED)
    query = request.GET.get("q", "").strip()
    publication_type = request.GET.get("type", "")
    if query:
        publications = publications.filter(Q(title__icontains=query) | Q(owner_student__display_name__icontains=query) | Q(owner_student__student_number__icontains=query))
    if publication_type:
        publications = publications.filter(publication_type_id=publication_type)
    sort_options = {
        "submitted_at": ("-submitted_at", "-created_at"),
        "student": ("owner_student__student_number", "-submitted_at"),
        "title": ("title", "-submitted_at"),
        "type": ("publication_type__display_order", "publication_type__display_name", "-submitted_at"),
    }
    sort = request.GET.get("sort", "submitted_at")
    publications = publications.order_by(*sort_options.get(sort, sort_options["submitted_at"]))
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "review/review_queue.html", {
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "result_total": publications.count(),
        "publication_types": PublicationType.objects.filter(is_active=True),
        "selected_type": publication_type,
        "query": query,
        "sort": sort,
    })


@login_required
def review_detail(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(_review_queryset(), pk=publication_id)
    return render(request, "review/review_detail.html", {
        "publication": publication,
        "return_form": ReturnForRevisionForm(),
        "revoke_form": RevokeApprovalForm(),
        "can_decide": publication.workflow_status == PublicationRecord.WorkflowStatus.SUBMITTED,
        "can_archive": publication.workflow_status == PublicationRecord.WorkflowStatus.APPROVED and is_official_publication(publication),
        "can_revoke": publication.workflow_status in {
            PublicationRecord.WorkflowStatus.APPROVED,
            PublicationRecord.WorkflowStatus.ARCHIVED,
        } and is_official_publication(publication),
    })


@login_required
@require_POST
def approve(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(PublicationRecord.objects.all(), pk=publication_id)
    try:
        approve_publication(actor=request.user, publication_id=publication.id)
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
    else:
        messages.success(request, "成果已核准；正式統計將從此納入此筆成果。")
    return redirect("review:detail", publication_id=publication.id)


@login_required
@require_POST
def return_publication(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(PublicationRecord.objects.all(), pk=publication_id)
    form = ReturnForRevisionForm(request.POST)
    if form.is_valid():
        try:
            return_for_revision(actor=request.user, publication_id=publication.id, reason=form.cleaned_data["reason"])
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        else:
            messages.success(request, "成果已退回學生修正。")
    else:
        messages.error(request, "退回資料無效。")
    return redirect("review:detail", publication_id=publication.id)


@login_required
@require_POST
def archive(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(PublicationRecord.objects.all(), pk=publication_id)
    try:
        archive_publication(actor=request.user, publication_id=publication.id)
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
    else:
        messages.success(request, "成果已封存；保留正式歷史統計，但不再出現在 active/public surfaces。")
    return redirect("review:detail", publication_id=publication.id)


@login_required
@require_POST
def revoke(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(PublicationRecord.objects.all(), pk=publication_id)
    form = RevokeApprovalForm(request.POST)
    if form.is_valid():
        try:
            revoke_approval(actor=request.user, publication_id=publication.id, reason=form.cleaned_data["reason"])
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        else:
            messages.success(request, "已撤銷核准；完整審核與稽核歷史已保留。")
    else:
        messages.error(request, "請填寫撤銷原因並完成確認。")
    return redirect("review:detail", publication_id=publication.id)


@login_required
def archive_list(request):
    _require_review_role(request)
    archive_transition = PublicationTransition.objects.filter(
        publication_id=OuterRef("pk"),
        to_status=PublicationRecord.WorkflowStatus.ARCHIVED,
    ).order_by("-created_at")
    publications = _review_queryset().filter(
        workflow_status=PublicationRecord.WorkflowStatus.ARCHIVED
    ).annotate(
        archived_at=Subquery(archive_transition.values("created_at")[:1]),
        archived_by_username=Subquery(archive_transition.values("actor__username")[:1]),
    ).order_by("-archived_at", "title")
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "review/archive_list.html", {
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    })


@login_required
def publication_settings(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(
        official_publications(),
        pk=publication_id,
        workflow_status=PublicationRecord.WorkflowStatus.APPROVED,
    )
    if request.method == "POST":
        form = PublicationSettingsForm(request.POST)
        if form.is_valid():
            set_visibility(actor=request.user, publication_id=publication.id, visibility_scope=form.cleaned_data["visibility_scope"])
            set_published(actor=request.user, publication_id=publication.id, is_published=form.cleaned_data["is_published"])
            messages.success(request, "發佈與可見範圍設定已更新。")
            return redirect("review:detail", publication_id=publication.id)
    else:
        form = PublicationSettingsForm(initial={"is_published": publication.is_published, "visibility_scope": publication.visibility_scope})
    return render(request, "review/publication_settings.html", {"publication": publication, "form": form})
