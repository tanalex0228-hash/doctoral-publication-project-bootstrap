import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SourceDocument(models.Model):
    class DocumentType(models.TextChoices):
        ARTICLE_FULLTEXT = "article_fulltext", "論文全文"
        ACCEPTANCE_LETTER = "acceptance_letter", "接受函"
        JOURNAL_PROOF = "journal_proof", "期刊佐證"
        INDEX_PROOF = "index_proof", "索引佐證"
        CONFERENCE_PROOF = "conference_proof", "會議佐證"
        OTHER = "other", "其他"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey("publications.PublicationRecord", on_delete=models.PROTECT, related_name="documents")
    document_type = models.CharField(max_length=24, choices=DocumentType.choices, default=DocumentType.OTHER, db_index=True)
    original_filename = models.CharField(max_length=500, db_index=True)
    storage_key = models.CharField(max_length=500, unique=True)
    mime_type = models.CharField(max_length=100, db_index=True)
    file_size = models.BigIntegerField()
    checksum_sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_documents")
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    supersedes = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="replacements")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["publication", "checksum_sha256"], name="uq_publication_checksum"), models.CheckConstraint(condition=models.Q(file_size__gt=0), name="ck_document_size_positive")]
        indexes = [models.Index(fields=["publication", "is_active"], name="idx_doc_publication_active")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            immutable = ("publication_id", "storage_key", "checksum_sha256", "uploaded_by_id", "original_filename", "mime_type", "file_size", "supersedes_id")
            if any(getattr(original, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Evidence provenance fields are immutable; create a replacement version instead.")
        super().save(*args, **kwargs)
