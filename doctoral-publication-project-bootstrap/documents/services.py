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


def _prepare(upload):
    filename = Path(upload.name).name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED: raise ValidationError("Only PDF, JPG/JPEG, and PNG evidence files are accepted.")
    data = upload.read()
    if not data or len(data) > MAX_FILE_SIZE: raise ValidationError("Evidence file must be non-empty and no larger than 25 MB.")
    detected = _sniff(data)
    if detected != ALLOWED[extension]: raise ValidationError("File extension and detected MIME type do not match.")
    declared = getattr(upload, "content_type", None)
    if declared and declared != detected: raise ValidationError("Declared MIME type does not match file content.")
    return filename, data, detected, hashlib.sha256(data).hexdigest()


@transaction.atomic
def upload_document(*, actor, publication, upload, document_type=SourceDocument.DocumentType.OTHER, request_id=None, supersedes=None):
    editable_statuses = {publication.WorkflowStatus.DRAFT, publication.WorkflowStatus.RETURNED}
    if publication.workflow_status not in editable_statuses or not (can_edit_publication(actor, publication) or is_staff_actor(actor)):
        raise PermissionDenied("Evidence may only be uploaded to a draft or returned publication by its owner or staff.")
    filename, data, mime_type, checksum = _prepare(upload)
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


def open_document_for_download(*, actor, document):
    if not can_download_document(actor, document): raise PermissionDenied("Document is not available to this actor.")
    return default_storage.open(document.storage_key, "rb")
