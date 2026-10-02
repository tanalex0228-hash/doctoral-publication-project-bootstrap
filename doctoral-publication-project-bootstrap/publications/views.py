from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django import forms as django_forms
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from documents.forms import DocumentUploadForm
from doctoral_students.models import DoctoralStudentProfile
from taxonomy.models import PublicationType
from .forms import (
    ConferenceDetailForm, JournalArticleDetailForm, PublicationAuthorForm,
    PublicationForm, PublicationTypeSelectionForm, author_form_values, publication_form_values,
)
from .models import ConferenceDetail, JournalArticleDetail, PublicationAuthor, PublicationRecord
from .permissions import can_edit_publication
from .querysets import is_official_publication
from .services import (
    add_author, create_revision, create_student_publication, delete_author,
    move_author, save_conference_detail, save_journal_article_detail,
    set_publication_sdgs, submit_publication, update_author, update_publication,
    withdraw_publication,
)
from .type_codes import CONFERENCE_TYPE_SLUGS, JOURNAL_TYPE_SLUGS, publication_detail_kind


def _student_for(request):
    try:
        return request.user.doctoral_profile
    except DoctoralStudentProfile.DoesNotExist as error:
        raise Http404("Student profile not found.") from error


def _owned_publication(request, publication_id):
    return get_object_or_404(
        PublicationRecord.objects.select_related(
            "owner_student", "publication_type", "journal_detail", "journal_detail__publication_country",
            "conference_detail", "conference_detail__location_country",
        ).prefetch_related(
            "authors", "indices", "research_fields", "documents", "sdg_assignments__goal",
            "conference_detail__participant_country_assignments__country",
            "conference_detail__presentation_mode_assignments__mode", "review_decisions",
        ).filter(owner_student=_student_for(request)),
        pk=publication_id,
    )


def _editable_publication(request, publication_id):
    publication = _owned_publication(request, publication_id)
    if not can_edit_publication(request.user, publication):
        raise Http404("Publication is unavailable for editing.")
    return publication


def _type_for_kind(kind):
    """Resolve only the established taxonomy aliases used by the business UI."""
    slugs = JOURNAL_TYPE_SLUGS if kind == "journal" else CONFERENCE_TYPE_SLUGS
    return get_object_or_404(
        PublicationType.objects.filter(is_active=True, slug__in=slugs).order_by("display_order", "display_name")
    )


def _apply_business_labels(form, kind):
    """Keep shared storage fields in the vocabulary of the selected workflow."""
    if kind == "conference":
        form.fields["title"].label = "成果名稱"
        form.fields["journal_or_conference_name"].label = "學術會議名"
    else:
        form.fields["journal_or_conference_name"].label = "期刊名"


def _combined_form_context(*, form, detail_form, kind, publication=None, selected_type=None, page_title, submit_label):
    _apply_business_labels(form, kind)
    form.fields["publication_type"].widget = django_forms.HiddenInput()
    return {
        "form": form,
        "detail_form": detail_form,
        "detail_kind": kind,
        "hidden_root_fields": (
            {"doi", "issn", "volume", "issue", "pages_or_article_number", "publication_stage",
             "submitted_to_journal_date", "accepted_date", "publication_date"}
            if kind == "conference" else set()
        ),
        "page_title": page_title,
        "submit_label": submit_label,
        "selected_type": selected_type,
        "publication": publication,
    }


def _save_combined_detail(*, actor, publication, kind, detail_form):
    if kind == "journal":
        save_journal_article_detail(
            actor=actor, publication_id=publication.id, **_form_model_values(detail_form),
        )
    else:
        save_conference_detail(
            actor=actor, publication_id=publication.id,
            participant_countries=detail_form.cleaned_data["participant_countries"],
            presentation_modes=detail_form.cleaned_data["presentation_modes"],
            **_form_model_values(detail_form),
        )
    set_publication_sdgs(actor=actor, publication_id=publication.id, goals=detail_form.cleaned_data["sdgs"])


@login_required
def publication_typed_create(request, kind):
    """One transactional student workflow for a journal or conference record."""
    selected_type = _type_for_kind(kind)
    detail_class = JournalArticleDetailForm if kind == "journal" else ConferenceDetailForm
    if request.method == "POST":
        form = PublicationForm(request.POST)
        detail_form = detail_class(request.POST)
        if form.is_valid() and detail_form.is_valid():
            values, indices, research_fields = publication_form_values(form)
            with transaction.atomic():
                publication = create_student_publication(
                    actor=request.user, owner_student=_student_for(request), indices=indices,
                    research_fields=research_fields, **values,
                )
                _save_combined_detail(actor=request.user, publication=publication, kind=kind, detail_form=detail_form)
            messages.success(request, "成果與專屬明細已建立。下一步請新增作者與上傳佐證文件。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = PublicationForm(initial={"publication_type": selected_type})
        detail_form = detail_class()
    return render(request, "publications/publication_form.html", _combined_form_context(
        form=form, detail_form=detail_form, kind=kind, selected_type=selected_type,
        page_title="新增期刊論文" if kind == "journal" else "新增學術會議與發表", submit_label="建立成果",
    ))


@login_required
def publication_create(request):
    selected_type = None
    selected_type_id = request.POST.get("publication_type") if request.method == "POST" else request.GET.get("publication_type")
    if selected_type_id:
        selected_type = get_object_or_404(PublicationType.objects.filter(is_active=True), pk=selected_type_id)
    detail_kind = publication_detail_kind(selected_type) if selected_type else None

    # Preserve the existing generic endpoint contract for older clients and
    # non-RC4 taxonomy values. The new wizard explicitly submits type_flow.
    if request.method == "POST" and not request.POST.get("type_flow"):
        form = PublicationForm(request.POST)
        if form.is_valid():
            values, indices, research_fields = publication_form_values(form)
            publication = create_student_publication(actor=request.user, owner_student=_student_for(request), indices=indices, research_fields=research_fields, **values)
            messages.success(request, "成果設定檔已建立。接著可新增作者與上傳佐證文件。")
            return redirect("publications:detail", publication_id=publication.id)
        return render(request, "publications/publication_form.html", {"form": form, "page_title": "新增成果", "submit_label": "建立成果"})

    if request.method == "GET" and not selected_type:
        return render(request, "publications/publication_form.html", {
            "type_selection_form": PublicationTypeSelectionForm(), "page_title": "新增成果",
        })

    if detail_kind:
        if request.method == "POST" and request.POST.get("type_flow"):
            form = PublicationForm(request.POST)
            detail_form = JournalArticleDetailForm(request.POST) if detail_kind == "journal" else ConferenceDetailForm(request.POST)
            if form.is_valid() and detail_form.is_valid():
                values, indices, research_fields = publication_form_values(form)
                with transaction.atomic():
                    publication = create_student_publication(
                        actor=request.user, owner_student=_student_for(request), indices=indices,
                        research_fields=research_fields, **values,
                    )
                    _save_combined_detail(actor=request.user, publication=publication, kind=detail_kind, detail_form=detail_form)
                messages.success(request, "成果與專屬明細已建立。接著可新增作者與上傳佐證文件。")
                return redirect("publications:detail", publication_id=publication.id)
        else:
            form = PublicationForm(initial={"publication_type": selected_type})
            detail_form = JournalArticleDetailForm() if detail_kind == "journal" else ConferenceDetailForm()
        return render(request, "publications/publication_form.html", _combined_form_context(
            form=form, detail_form=detail_form, kind=detail_kind, selected_type=selected_type,
            page_title="新增期刊論文" if detail_kind == "journal" else "新增學術會議與發表", submit_label="建立成果",
        ))

    form = PublicationForm(initial={"publication_type": selected_type} if selected_type else None)
    return render(request, "publications/publication_form.html", {"form": form, "page_title": "新增成果", "submit_label": "建立成果"})


@login_required
def publication_detail(request, publication_id):
    publication = _owned_publication(request, publication_id)
    latest_return = publication.review_decisions.filter(action="return").order_by("-created_at").first()
    return render(request, "publications/publication_detail.html", {
        "publication": publication,
        "editable": can_edit_publication(request.user, publication),
        "latest_return": latest_return,
        "documents": publication.documents.filter(is_active=True),
        "document_upload_form": DocumentUploadForm(),
        "can_create_revision": is_official_publication(publication) and publication.owner_student.user_id == request.user.id,
        "detail_kind": publication_detail_kind(publication.publication_type),
    })


@login_required
def publication_edit(request, publication_id):
    publication = _editable_publication(request, publication_id)
    if request.method == "POST":
        form = PublicationForm(request.POST, instance=publication)
        if form.is_valid():
            values, indices, research_fields = publication_form_values(form)
            update_publication(actor=request.user, publication_id=publication.id, indices=indices, research_fields=research_fields, **values)
            messages.success(request, "成果資料已更新。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = PublicationForm(instance=publication)
    return render(request, "publications/publication_form.html", {"form": form, "page_title": "編輯成果", "submit_label": "儲存變更", "publication": publication})


@login_required
def publication_typed_edit(request, publication_id, kind):
    """Edit root and subtype fields together; workflow permissions remain service-enforced."""
    publication = _editable_publication(request, publication_id)
    if publication_detail_kind(publication.publication_type) != kind:
        raise Http404("This business form is unavailable for the selected publication.")
    detail_class = JournalArticleDetailForm if kind == "journal" else ConferenceDetailForm
    try:
        detail = publication.journal_detail if kind == "journal" else publication.conference_detail
    except (JournalArticleDetail.DoesNotExist, ConferenceDetail.DoesNotExist):
        detail = None
    if request.method == "POST":
        form = PublicationForm(request.POST, instance=publication)
        detail_form = detail_class(request.POST, instance=detail)
        if form.is_valid() and detail_form.is_valid():
            values, indices, research_fields = publication_form_values(form)
            with transaction.atomic():
                publication = update_publication(
                    actor=request.user, publication_id=publication.id, indices=indices,
                    research_fields=research_fields, **values,
                )
                _save_combined_detail(actor=request.user, publication=publication, kind=kind, detail_form=detail_form)
            messages.success(request, "成果與專屬明細已更新。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = PublicationForm(instance=publication)
        detail_form = detail_class(instance=detail)
    return render(request, "publications/publication_form.html", _combined_form_context(
        form=form, detail_form=detail_form, kind=kind, publication=publication,
        selected_type=publication.publication_type,
        page_title="編輯期刊論文" if kind == "journal" else "編輯學術會議與發表", submit_label="儲存變更",
    ))


def _form_model_values(form):
    return {
        field.name: form.cleaned_data[field.name]
        for field in form._meta.model._meta.fields
        if field.name not in {"id", "publication"} and field.name in form.cleaned_data
    }


@login_required
def journal_detail_edit(request, publication_id):
    publication = _editable_publication(request, publication_id)
    if publication_detail_kind(publication.publication_type) != "journal":
        raise Http404("Journal detail is unavailable for this publication type.")
    try:
        instance = publication.journal_detail
    except JournalArticleDetail.DoesNotExist:
        instance = None
    if request.method == "POST":
        form = JournalArticleDetailForm(request.POST, instance=instance)
        if form.is_valid():
            save_journal_article_detail(actor=request.user, publication_id=publication.id, **_form_model_values(form))
            set_publication_sdgs(actor=request.user, publication_id=publication.id, goals=form.cleaned_data["sdgs"])
            messages.success(request, "期刊論文明細已更新。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = JournalArticleDetailForm(instance=instance)
    return render(request, "publications/detail_form.html", {
        "form": form, "publication": publication, "detail_kind": "journal", "page_title": "期刊論文明細",
    })


@login_required
def conference_detail_edit(request, publication_id):
    publication = _editable_publication(request, publication_id)
    if publication_detail_kind(publication.publication_type) != "conference":
        raise Http404("Conference detail is unavailable for this publication type.")
    try:
        instance = publication.conference_detail
    except ConferenceDetail.DoesNotExist:
        instance = None
    if request.method == "POST":
        form = ConferenceDetailForm(request.POST, instance=instance)
        if form.is_valid():
            save_conference_detail(
                actor=request.user, publication_id=publication.id,
                participant_countries=form.cleaned_data["participant_countries"],
                presentation_modes=form.cleaned_data["presentation_modes"], **_form_model_values(form),
            )
            set_publication_sdgs(actor=request.user, publication_id=publication.id, goals=form.cleaned_data["sdgs"])
            messages.success(request, "學術會議明細已更新。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = ConferenceDetailForm(instance=instance)
    return render(request, "publications/detail_form.html", {
        "form": form, "publication": publication, "detail_kind": "conference", "page_title": "學術會議與發表明細",
    })


@login_required
def author_create(request, publication_id):
    publication = _editable_publication(request, publication_id)
    if request.method == "POST":
        form = PublicationAuthorForm(request.POST)
        if form.is_valid():
            add_author(actor=request.user, publication_id=publication.id, **author_form_values(form))
            messages.success(request, "作者已新增。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = PublicationAuthorForm()
    return render(request, "publications/author_form.html", {"form": form, "publication": publication, "page_title": "新增作者", "submit_label": "新增作者"})


@login_required
def author_edit(request, publication_id, author_id):
    publication = _editable_publication(request, publication_id)
    author = get_object_or_404(PublicationAuthor, pk=author_id, publication=publication)
    if request.method == "POST":
        form = PublicationAuthorForm(request.POST, instance=author)
        if form.is_valid():
            update_author(actor=request.user, author_id=author.id, **author_form_values(form))
            messages.success(request, "作者資料已更新。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = PublicationAuthorForm(instance=author)
    return render(request, "publications/author_form.html", {"form": form, "publication": publication, "page_title": "編輯作者", "submit_label": "儲存作者"})


@login_required
@require_POST
def author_delete(request, publication_id, author_id):
    publication = _editable_publication(request, publication_id)
    author = get_object_or_404(PublicationAuthor, pk=author_id, publication=publication)
    delete_author(actor=request.user, author_id=author.id)
    messages.success(request, "作者已刪除。")
    return redirect("publications:detail", publication_id=publication.id)


@login_required
@require_POST
def author_move(request, publication_id, author_id, direction):
    publication = _editable_publication(request, publication_id)
    author = get_object_or_404(PublicationAuthor, pk=author_id, publication=publication)
    try:
        move_author(actor=request.user, author_id=author.id, direction=direction)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect("publications:detail", publication_id=publication.id)


@login_required
@require_POST
def publication_submit(request, publication_id):
    publication = _editable_publication(request, publication_id)
    try:
        submit_publication(actor=request.user, publication_id=publication.id)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, "成果已送交審核，等待秘書處理。")
    return redirect("publications:detail", publication_id=publication.id)


@login_required
@require_POST
def publication_revision_create(request, publication_id):
    publication = _owned_publication(request, publication_id)
    try:
        revision = create_revision(actor=request.user, publication_id=publication.id)
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        return redirect("publications:detail", publication_id=publication.id)
    messages.success(request, "已建立待審修訂版本；目前正式版本在修訂核准前不會改變。")
    return redirect("publications:detail", publication_id=revision.id)


@login_required
@require_POST
def publication_withdraw(request, publication_id):
    publication = _owned_publication(request, publication_id)
    try:
        withdraw_publication(actor=request.user, publication_id=publication.id)
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        return redirect("publications:detail", publication_id=publication.id)
    messages.success(request, "草稿已撤回；為維護稽核歷史，系統不會永久刪除此成果。")
    return redirect("dashboard:student")
