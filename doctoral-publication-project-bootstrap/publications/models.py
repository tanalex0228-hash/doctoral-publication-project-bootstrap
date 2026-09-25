import re
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def normalize_text(value):
    return " ".join((value or "").split()).casefold()


def normalize_doi(value):
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(dx\\.)?doi\\.org/", "", value)
    value = re.sub(r"^doi:\\s*", "", value)
    return value or None


class PublicationSeries(models.Model):
    """One logical scholarly result with one optionally current official version."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_student = models.ForeignKey("doctoral_students.DoctoralStudentProfile", on_delete=models.PROTECT, related_name="publication_series")
    current_official_version = models.ForeignKey(
        "PublicationRecord", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="current_for_series",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["owner_student", "current_official_version"], name="idx_series_official")]
        verbose_name = "成果系列"
        verbose_name_plural = "成果系列"


class PublicationRecord(models.Model):
    class WorkflowStatus(models.TextChoices):
        DRAFT = "draft", "草稿"
        SUBMITTED = "submitted", "已送審"
        RETURNED = "returned", "已退回"
        APPROVED = "approved", "已核准"
        ARCHIVED = "archived", "已封存"
        WITHDRAWN = "withdrawn", "已撤回"
        REVOKED = "revoked", "已撤銷核准"

    class VisibilityScope(models.TextChoices):
        PUBLIC = "public", "公開"
        DEPARTMENT_ALL = "department_all", "系所全體"
        DEPARTMENT_CURRENT = "department_current", "系所在學"
        OWNER_FACULTY = "owner_faculty", "本人與全體教職員"
        OWNER_ADVISOR = "owner_advisor", "本人與指導教授"
        STAFF_ONLY = "staff_only", "工作人員限定"

    class PublicationStage(models.TextChoices):
        SUBMITTED = "submitted", "投稿中"
        ACCEPTED = "accepted", "已接受"
        ONLINE_FIRST = "online_first", "線上先行"
        PUBLISHED = "published", "正式發表"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(PublicationSeries, on_delete=models.PROTECT, related_name="versions")
    is_revision = models.BooleanField(default=False, db_index=True)
    owner_student = models.ForeignKey("doctoral_students.DoctoralStudentProfile", on_delete=models.PROTECT, related_name="publications")
    publication_type = models.ForeignKey("taxonomy.PublicationType", on_delete=models.PROTECT, related_name="publications")
    title = models.CharField(max_length=500, db_index=True)
    normalized_title = models.CharField(max_length=500, db_index=True, editable=False)
    abstract = models.TextField(blank=True)
    journal_or_conference_name = models.CharField(max_length=500, blank=True, db_index=True)
    language = models.CharField(max_length=16, default="zh-Hant", db_index=True)
    doi = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    normalized_doi = models.CharField(max_length=255, null=True, blank=True, editable=False)
    issn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    volume = models.CharField(max_length=32, blank=True)
    issue = models.CharField(max_length=32, blank=True)
    pages_or_article_number = models.CharField(max_length=64, blank=True)
    publication_stage = models.CharField(max_length=16, choices=PublicationStage.choices, default=PublicationStage.PUBLISHED, db_index=True)
    submitted_to_journal_date = models.DateField(null=True, blank=True, db_index=True)
    accepted_date = models.DateField(null=True, blank=True, db_index=True)
    publication_date = models.DateField(null=True, blank=True, db_index=True)
    workflow_status = models.CharField(max_length=16, choices=WorkflowStatus.choices, default=WorkflowStatus.DRAFT, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    visibility_scope = models.CharField(max_length=24, choices=VisibilityScope.choices, default=VisibilityScope.OWNER_ADVISOR, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_publications")
    approval_revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approval_revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="revoked_publications")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_publications")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_publications")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    indices = models.ManyToManyField("taxonomy.PublicationIndex", through="PublicationIndexAssignment", blank=True)
    research_fields = models.ManyToManyField("taxonomy.ResearchField", through="PublicationFieldAssignment", blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner_student", "workflow_status"], name="idx_owner_status"),
            models.Index(fields=["workflow_status", "publication_date", "publication_type"], name="idx_staff_stats"),
            models.Index(fields=["workflow_status", "is_published", "visibility_scope"], name="idx_public_gate"),
            models.Index(fields=["series", "workflow_status"], name="idx_series_status"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["normalized_doi"], condition=Q(normalized_doi__isnull=False), name="uq_doi_normalized"),
            models.UniqueConstraint(
                fields=["series"],
                condition=Q(is_revision=True, workflow_status__in=["draft", "submitted", "returned"]),
                name="uq_pending_revision_series",
            ),
        ]
        verbose_name = "成果紀錄"
        verbose_name_plural = "成果紀錄"

    def save(self, *args, **kwargs):
        self.normalized_title = normalize_text(self.title)
        self.normalized_doi = normalize_doi(self.doi)
        super().save(*args, **kwargs)

    def clean(self):
        if self.is_published and self.workflow_status not in {self.WorkflowStatus.APPROVED, self.WorkflowStatus.ARCHIVED}:
            raise ValidationError("Only approved publications may be published on the platform.")

    def __str__(self): return self.title


class PublicationAuthor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey(PublicationRecord, on_delete=models.PROTECT, related_name="authors")
    display_name = models.CharField(max_length=200, db_index=True)
    affiliation = models.CharField(max_length=500, blank=True, db_index=True)
    author_order = models.PositiveSmallIntegerField()
    is_corresponding_author = models.BooleanField(default=False, db_index=True)
    linked_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_publications")
    linked_professor = models.ForeignKey("professors.Professor", on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_publications")
    orcid = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["publication", "author_order"], name="uq_author_order"), models.CheckConstraint(condition=Q(author_order__gte=1), name="ck_author_order_positive")]
        ordering = ["author_order"]
        verbose_name = "成果作者"
        verbose_name_plural = "成果作者"


class PublicationIndexAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey(PublicationRecord, on_delete=models.PROTECT)
    index = models.ForeignKey("taxonomy.PublicationIndex", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["publication", "index"], name="uq_publication_index")]
        verbose_name = "成果索引對照"
        verbose_name_plural = "成果索引對照"


class PublicationFieldAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey(PublicationRecord, on_delete=models.PROTECT)
    field = models.ForeignKey("taxonomy.ResearchField", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["publication", "field"], name="uq_publication_field")]
        verbose_name = "成果研究領域對照"
        verbose_name_plural = "成果研究領域對照"
