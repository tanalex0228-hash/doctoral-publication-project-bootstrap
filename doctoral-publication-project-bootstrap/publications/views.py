from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from documents.forms import DocumentUploadForm
from doctoral_students.models import DoctoralStudentProfile
from .forms import PublicationAuthorForm, PublicationForm, author_form_values, publication_form_values
from .models import PublicationAuthor, PublicationRecord
from .permissions import can_edit_publication
from .querysets import is_official_publication
from .services import add_author, create_revision, create_student_publication, delete_author, move_author, submit_publication, update_author, update_publication


def _student_for(request):
    try:
        return request.user.doctoral_profile
    except DoctoralStudentProfile.DoesNotExist as error:
        raise Http404("Student profile not found.") from error


def _owned_publication(request, publication_id):
    return get_object_or_404(PublicationRecord.objects.select_related("owner_student", "publication_type").filter(owner_student=_student_for(request)), pk=publication_id)


def _editable_publication(request, publication_id):
    publication = _owned_publication(request, publication_id)
    if not can_edit_publication(request.user, publication):
        raise Http404("Publication is unavailable for editing.")
    return publication


@login_required
def publication_create(request):
    if request.method == "POST":
        form = PublicationForm(request.POST)
        if form.is_valid():
            values, indices, research_fields = publication_form_values(form)
            publication = create_student_publication(actor=request.user, owner_student=_student_for(request), indices=indices, research_fields=research_fields, **values)
            messages.success(request, "成果設定檔已建立。接著可新增作者與上傳佐證文件。")
            return redirect("publications:detail", publication_id=publication.id)
    else:
        form = PublicationForm()
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
