import csv
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import OuterRef, Q, Subquery
from django.http import Http404, HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from config.pagination import paginate_queryset
from publications.models import PublicationRecord
from publications.permissions import is_staff_actor
from publications.querysets import is_official_publication, official_publications
from publications.services import set_published, set_visibility, trash_publication
from publications.type_codes import CONFERENCE_TYPE_SLUGS, JOURNAL_TYPE_SLUGS, publication_detail_kind
from reporting.secretary_exports import CONFERENCE_HEADERS, JOURNAL_HEADERS, conference_rows, journal_rows
from reporting.services import csv_safe_cell
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


def _filtered_review_publications(request, *, kind=None):
    """One filtered queryset for both the secretary list and its downloads."""
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
        "all",
        "trash",
    }
    if status not in allowed_statuses:
        status = PublicationRecord.WorkflowStatus.SUBMITTED
    if status == "trash":
        publications = publications.filter(is_trashed=True)
    elif status == "all":
        publications = publications.filter(is_trashed=False)
    else:
        publications = publications.filter(is_trashed=False, workflow_status=status)

    query = request.GET.get("q", "").strip()
    publication_type = request.GET.get("type", "")
    if query:
        publications = publications.filter(
            Q(title__icontains=query) | Q(owner_student__student_number__icontains=query)
        )
    if publication_type:
        publications = publications.filter(publication_type_id=publication_type)
    sort_options = {
        "submitted_at": ("-submitted_at", "-created_at"),
        "student": ("owner_student__student_number", "-submitted_at"),
        "title": ("title", "-submitted_at"),
        "type": ("publication_type__display_order", "publication_type__display_name", "-submitted_at"),
    }
    sort = request.GET.get("sort", "submitted_at")
    return publications.order_by(*sort_options.get(sort, sort_options["submitted_at"])), {
        "status": status,
        "query": query,
        "publication_type": publication_type,
        "sort": sort,
    }


def _csv_download(*, filename, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([csv_safe_cell(value) for value in row])
    return response


def _xlsx_download(*, filename, worksheet_title, headers, rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = worksheet_title[:31]
    worksheet.append(headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
    worksheet.freeze_panes = "A2"
    for row in rows:
        worksheet.append([csv_safe_cell(value) for value in row])
    worksheet.auto_filter.ref = worksheet.dimensions
    for index, column in enumerate(worksheet.columns, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = min(
            max((len(str(cell.value or "")) for cell in column), default=0) + 2, 40
        )
    stream = BytesIO()
    workbook.save(stream)
    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def _review_list(request, *, kind=None):
    _require_review_role(request)
    publications, filters = _filtered_review_publications(request, kind=kind)
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "review/review_queue.html", {
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "result_total": publications.count(),
        "publication_types": PublicationType.objects.filter(is_active=True),
        "selected_type": filters["publication_type"],
        "query": filters["query"],
        "sort": filters["sort"],
        "status": filters["status"],
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
def review_export(request, kind):
    _require_review_role(request)
    if kind not in {"journal", "conference"}:
        raise Http404("Export resource not found.")
    export_format = request.GET.get("format", "xlsx")
    if export_format not in {"csv", "xlsx"}:
        raise Http404("Export format not found.")
    publications, _ = _filtered_review_publications(request, kind=kind)
    if kind == "journal":
        headers, rows, filename, worksheet_title = (
            JOURNAL_HEADERS, journal_rows(publications), "filtered-journal-publications", "期刊論文清單",
        )
    else:
        headers, rows, filename, worksheet_title = (
            CONFERENCE_HEADERS, conference_rows(publications), "filtered-conference-publications", "學術會議出席清單",
        )
    if export_format == "csv":
        return _csv_download(filename=f"{filename}.csv", headers=headers, rows=rows)
    return _xlsx_download(filename=f"{filename}.xlsx", worksheet_title=worksheet_title, headers=headers, rows=rows)


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
