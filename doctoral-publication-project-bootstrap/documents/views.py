import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from publications.models import PublicationRecord
from publications.permissions import can_download_document, can_edit_publication
from .forms import DocumentUploadForm
from .models import SourceDocument
from .services import open_document_for_download, upload_document


logger = logging.getLogger("documents.security")


def _owned_publication(request, publication_id):
    return get_object_or_404(PublicationRecord.objects.filter(owner_student__user=request.user), pk=publication_id)


@login_required
@require_POST
def document_upload(request, publication_id):
    publication = _owned_publication(request, publication_id)
    if not can_edit_publication(request.user, publication):
        raise Http404("Publication is unavailable for document management.")
    form = DocumentUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            upload_document(actor=request.user, publication=publication, upload=form.cleaned_data["file"], document_type=form.cleaned_data["document_type"])
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, "; ".join(getattr(error, "messages", [str(error)])))
        except Exception:
            messages.error(request, "文件目前無法上傳，請稍後再試。")
        else:
            messages.success(request, "佐證文件已安全上傳。")
    else:
        messages.error(request, "文件上傳失敗，請確認檔案與文件類型。")
    return redirect("publications:detail", publication_id=publication.id)


@login_required
def document_download(request, document_id):
    document = get_object_or_404(SourceDocument.objects.select_related("publication", "publication__owner_student"), pk=document_id)
    if not can_download_document(request.user, document):
        logger.warning("document_download_denied user_id=%s document_id=%s", request.user.pk, document.id)
        raise Http404("Document not found.")
    try:
        stream = open_document_for_download(actor=request.user, document=document)
    except PermissionDenied as error:
        logger.warning("document_download_denied_after_check user_id=%s document_id=%s", request.user.pk, document.id)
        raise Http404("Document not found.") from error
    return FileResponse(stream, as_attachment=True, filename=document.original_filename, content_type=document.mime_type)
