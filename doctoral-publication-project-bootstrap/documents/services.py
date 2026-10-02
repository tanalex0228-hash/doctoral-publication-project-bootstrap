import hashlib
import os
import uuid
from pathlib import Path
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from audit.services import record_event
from publications.permissions import can_edit_publication, can_download_document, is_staff_actor
from .models import SourceDocument

MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _sniff(data):
    if data.startswith(b"%PDF-"): return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    return None


def _prepare(upload, *, document_type):
    filename = Path(upload.name).name
    extension = Path(filename).suffix.lower()
    is_conference_evidence = document_type == SourceDocument.DocumentType.CONFERENCE_EVIDENCE
    allowed = {".pdf": "application/pdf"} if is_conference_evidence else ALLOWED
    max_file_size = 10 * 1024 * 1024 if is_conference_evidence else MAX_FILE_SIZE
    if extension not in allowed:
        raise ValidationError("學術會議佐證僅接受 PDF 檔案。" if is_conference_evidence else "Only PDF, JPG/JPEG, and PNG evidence files are accepted.")
    data = upload.read()
    if not data or len(data) > max_file_size:
        raise ValidationError("學術會議佐證必須為非空白且不超過 10 MB 的 PDF 檔案。" if is_conference_evidence else "Evidence file must be non-empty and no larger than 25 MB.")
    detected = _sniff(data)
    if detected != allowed[extension]: raise ValidationError("File extension and detected MIME type do not match.")
    declared = getattr(upload, "content_type", None)
    if declared and declared != detected: raise ValidationError("Declared MIME type does not match file content.")
    return filename, data, detected, hashlib.sha256(data).hexdigest()


@transaction.atomic
def upload_document(*, actor, publication, upload, document_type=SourceDocument.DocumentType.OTHER, request_id=None, supersedes=None):
    editable_statuses = {publication.WorkflowStatus.DRAFT, publication.WorkflowStatus.RETURNED}
    if publication.workflow_status not in editable_statuses or not (can_edit_publication(actor, publication) or is_staff_actor(actor)):
        raise PermissionDenied("Evidence may only be uploaded to a draft or returned publication by its owner or staff.")
    filename, data, mime_type, checksum = _prepare(upload, document_type=document_type)
    if supersedes and (
        supersedes.publication_id != publication.id or not supersedes.is_active
    ):
        raise ValidationError("Only an active document of the same publication may be replaced.")
    if SourceDocument.objects.filter(publication=publication, checksum_sha256=checksum).exists():
        raise ValidationError("相同內容的佐證文件已存在，請勿重複上傳。")
    key = f"evidence/{uuid.uuid4().hex}"
    saved_key = default_storage.save(key, ContentFile(data))
    try:
        document = SourceDocument.objects.create(publication=publication, document_type=document_type, original_filename=filename,
            storage_key=saved_key, mime_type=mime_type, file_size=len(data), checksum_sha256=checksum, uploaded_by=actor, supersedes=supersedes)
        if supersedes:
            supersedes.is_active = False
            supersedes.save(update_fields=["is_active"])
    except Exception:
        default_storage.delete(saved_key)
        raise
    record_event(actor=actor, action="document.uploaded" if not supersedes else "document.replaced", target=document, request_id=request_id, metadata={"document_type": document_type})
    return document


@transaction.atomic
def retire_document(*, actor, document, request_id=None):
    """Hide an editable evidence version while retaining its provenance and audit trail."""
    publication = document.publication
    editable_statuses = {publication.WorkflowStatus.DRAFT, publication.WorkflowStatus.RETURNED}
    if (
        not document.is_active
        or publication.workflow_status not in editable_statuses
        or not (can_edit_publication(actor, publication) or is_staff_actor(actor))
    ):
        raise PermissionDenied("This evidence version cannot be removed in its current state.")
    document.is_active = False
    document.save(update_fields=["is_active"])
    record_event(
        actor=actor, action="document.retired", target=document, request_id=request_id,
        metadata={"publication_id": str(publication.id), "document_type": document.document_type},
    )
    return document


def open_document_for_download(*, actor, document):
    if not can_download_document(actor, document): raise PermissionDenied("Document is not available to this actor.")
    return default_storage.open(document.storage_key, "rb")
