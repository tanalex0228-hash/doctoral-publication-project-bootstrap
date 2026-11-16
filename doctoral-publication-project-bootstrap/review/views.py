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
from publications.services import set_published, set_visibility, trash_publication
from publications.type_codes import CONFERENCE_TYPE_SLUGS, JOURNAL_TYPE_SLUGS, publication_detail_kind
from taxonomy.models import PublicationType
from .forms import PublicationSettingsForm, ReturnForRevisionForm, RevokeApprovalForm
from .models import PublicationTransition
from .services import approve_publication, archive_publication, restore_publication, return_for_revision, revoke_approval


def _require_review_role(request):
    if not is_staff_actor(request.user):
        raise Http404("Review resource not found.")


def _review_queryset():
    return PublicationRecord.objects.select_related(
        "owner_student", "publication_type", "journal_detail", "journal_detail__publication_country",
        "conference_detail", "conference_detail__location_country",
    ).prefetch_related(
        "owner_student__advisor_relations__professor", "authors", "indices", "research_fields", "documents",
        "review_decisions", "transitions", "sdg_assignments__goal",
        "conference_detail__participant_country_assignments__country",
        "conference_detail__presentation_mode_assignments__mode",
    )


@login_required
def _review_list(request, *, kind=None):
    _require_review_role(request)
    publications = _review_queryset().filter(is_purged=False)
    if kind == "journal":
        publications = publications.filter(publication_type__slug__in=JOURNAL_TYPE_SLUGS)
    elif kind == "conference":
        publications = publications.filter(publication_type__slug__in=CONFERENCE_TYPE_SLUGS)
    status = request.GET.get("status", PublicationRecord.WorkflowStatus.SUBMITTED)
    allowed_statuses = {
        PublicationRecord.WorkflowStatus.SUBMITTED,
        PublicationRecord.WorkflowStatus.RETURNED,
        PublicationRecord.WorkflowStatus.APPROVED,
        "trash",
    }
    if status not in allowed_statuses:
        status = PublicationRecord.WorkflowStatus.SUBMITTED
    publications = publications.filter(is_trashed=status == "trash")
    if status != "trash":
        publications = publications.filter(workflow_status=status)
    query = request.GET.get("q", "").strip()
    publication_type = request.GET.get("type", "")
    if query:
        publications = publications.filter(Q(title__icontains=query))
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
        "status": status,
        "kind": kind,
        "page_title": "期刊論文清單" if kind == "journal" else "學術會議清單" if kind == "conference" else "秘書審核清單",
    })


@login_required
def review_queue(request):
    """Compatibility queue: all types, initially limited to pending review."""
    return _review_list(request)


@login_required
def journal_list(request):
    return _review_list(request, kind="journal")


@login_required
def conference_list(request):
    return _review_list(request, kind="conference")


@login_required
def review_detail(request, publication_id):
    _require_review_role(request)
    publication = get_object_or_404(_review_queryset().filter(is_purged=False), pk=publication_id)
    return render(request, "review/review_detail.html", {
        "publication": publication,
        "return_form": ReturnForRevisionForm(),
        "revoke_form": RevokeApprovalForm(),
        "can_decide": publication.workflow_status == PublicationRecord.WorkflowStatus.SUBMITTED,
        "detail_kind": publication_detail_kind(publication.publication_type),
    })


@login_required
@require_POST
def trash_selected(request):
    _require_review_role(request)
    publication_ids = request.POST.getlist("publication_ids")
    if not publication_ids:
        messages.error(request, "請先選取至少一筆成果。")
    else:
        completed = 0
        for publication in PublicationRecord.objects.filter(pk__in=publication_ids, is_trashed=False):
            try:
                trash_publication(actor=request.user, publication_id=publication.id)
            except (PermissionDenied, ValidationError) as error:
                messages.error(request, f"{publication.title}：{error}")
            else:
                completed += 1
        if completed:
            messages.success(request, f"已將 {completed} 筆成果移至垃圾桶；資料、文件與稽核紀錄均保留。")
    return redirect(request.POST.get("next") or "review:queue")


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
        messages.success(request, "成果已封存；保留正式歷史統計。若維持已發佈且公開，仍可出現在公開成果頁。")
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
        workflow_status__in=(
            PublicationRecord.WorkflowStatus.APPROVED,
            PublicationRecord.WorkflowStatus.ARCHIVED,
        ),
    )
    if request.method == "POST":
        form = PublicationSettingsForm(request.POST)
        if form.is_valid():
            if publication.workflow_status == PublicationRecord.WorkflowStatus.ARCHIVED and form.cleaned_data["is_published"]:
                publication = restore_publication(actor=request.user, publication_id=publication.id)
            set_visibility(actor=request.user, publication_id=publication.id, visibility_scope=form.cleaned_data["visibility_scope"])
            set_published(actor=request.user, publication_id=publication.id, is_published=form.cleaned_data["is_published"])
            messages.success(request, "發佈與可見範圍設定已更新。")
            return redirect("review:detail", publication_id=publication.id)
    else:
        form = PublicationSettingsForm(initial={"is_published": publication.is_published, "visibility_scope": publication.visibility_scope})
    return render(request, "review/publication_settings.html", {"publication": publication, "form": form})
