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


class Country(models.Model):
    """Maintained country reference; identity is never stored as free text."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=12, unique=True, db_index=True)
    zh_name = models.CharField(max_length=100, db_index=True)
    en_name = models.CharField(max_length=150, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "zh_name", "code"]
        verbose_name = "國家／地區"
        verbose_name_plural = "國家／地區"

    def __str__(self):
        return f"{self.code}－{self.zh_name}" if self.en_name else f"{self.code}－{self.zh_name}"


class SustainableDevelopmentGoal(models.Model):
    """Stable SDG reference data, including the mutually-exclusive NONE code."""
    class Code(models.TextChoices):
        SDG01 = "SDG01", "SDG01 消除貧窮"
        SDG02 = "SDG02", "SDG02 消除飢餓"
        SDG03 = "SDG03", "SDG03 健康與福祉"
        SDG04 = "SDG04", "SDG04 優質教育"
        SDG05 = "SDG05", "SDG05 性別平權"
        SDG06 = "SDG06", "SDG06 淨水及衛生"
        SDG07 = "SDG07", "SDG07 可負擔能源"
        SDG08 = "SDG08", "SDG08 合適的工作及經濟成長"
        SDG09 = "SDG09", "SDG09 工業、創新及基礎建設"
        SDG10 = "SDG10", "SDG10 減少不平等"
        SDG11 = "SDG11", "SDG11 永續城鄉"
        SDG12 = "SDG12", "SDG12 責任消費及生產"
        SDG13 = "SDG13", "SDG13 氣候行動"
        SDG14 = "SDG14", "SDG14 海洋生態"
        SDG15 = "SDG15", "SDG15 陸域生態"
        SDG16 = "SDG16", "SDG16 和平、正義及健全制度"
        SDG17 = "SDG17", "SDG17 夥伴關係"
        NONE = "NONE", "無"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=8, choices=Code.choices, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "code"]
        verbose_name = "永續發展目標"
        verbose_name_plural = "永續發展目標"

    def __str__(self):
        return self.display_name


class PublicationSDGAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey(PublicationRecord, on_delete=models.PROTECT, related_name="sdg_assignments")
    goal = models.ForeignKey(SustainableDevelopmentGoal, on_delete=models.PROTECT, related_name="publication_assignments")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["publication", "goal"], name="uq_publication_sdg")]
        verbose_name = "成果 SDG 對照"
        verbose_name_plural = "成果 SDG 對照"


class JournalArticleDetail(models.Model):
    class JournalType(models.TextChoices):
        TSSCI = "tssci", "TSSCI"
        SCI = "sci", "SCI"
        SSCI = "ssci", "SSCI"
        EI = "ei", "EI"
        AHCI = "ahci", "A&HCI"
        THCI = "thci", "THCI"
        SCOPUS = "scopus", "Scopus"
        COLLEGE_RECOGNIZED = "college_recognized", "各院認可之優良期刊"
        OTHER = "other", "其他"

    class InternationalJournalRank(models.TextChoices):
        TOP_10 = "top_10", "前 10%"
        TOP_10_25 = "top_10_25", "10–25%"
        TOP_25_50 = "top_25_50", "25–50%"
        BOTTOM_50_OR_UNRANKED = "bottom_50_or_unranked", "後 50% 或未有排名"

    class TaiwanJournalLevel(models.TextChoices):
        LEVEL_1 = "level_1", "第一級"
        LEVEL_2 = "level_2", "第二級"
        OTHER = "other", "非第一級及第二級"

    class StudentAuthorOrder(models.TextChoices):
        FIRST = "first", "第一作者"
        SECOND = "second", "第二作者"
        THIRD = "third", "第三作者"
        FOURTH_OR_LATER = "fourth_or_later", "第四作者（含）以後"

    class StudentAuthorAttribute(models.TextChoices):
        FIRST_AUTHOR = "first_author", "第一作者"
        CORRESPONDING_AUTHOR = "corresponding_author", "通訊作者"
        CO_FIRST_OR_CO_CORRESPONDING = "co_first_or_co_corresponding", "共同第一作者或共同通訊作者"
        NEITHER = "neither", "非第一或通訊作者"

    class PublicationMedium(models.TextChoices):
        PAPER = "paper", "紙本期刊"
        ELECTRONIC = "electronic", "電子期刊"
        PAPER_AND_ELECTRONIC = "paper_and_electronic", "紙本及電子期刊"

    class PaperNature(models.TextChoices):
        ACADEMIC = "academic", "學術"
        EDUCATIONAL = "educational", "學習教育"
        PRACTICAL = "practical", "實務"

    class PaperAttribute(models.TextChoices):
        THEORETICAL = "theoretical", "理論"
        APPLIED = "applied", "應用"
        OTHER = "other", "其他"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.OneToOneField(PublicationRecord, on_delete=models.PROTECT, related_name="journal_detail")
    journal_type = models.CharField(max_length=24, choices=JournalType.choices, db_index=True)
    legacy_journal_type = models.CharField(max_length=255, blank=True, editable=False)
    international_journal_rank = models.CharField(max_length=24, choices=InternationalJournalRank.choices, blank=True)
    impact_factor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    taiwan_journal_level = models.CharField(max_length=16, choices=TaiwanJournalLevel.choices, blank=True)
    custom_journal_type = models.CharField(max_length=255, blank=True)
    student_author_order = models.CharField(max_length=20, choices=StudentAuthorOrder.choices)
    student_author_order_reason = models.CharField(max_length=500, blank=True)
    student_author_attribute = models.CharField(max_length=32, choices=StudentAuthorAttribute.choices)
    is_student_corresponding_author = models.BooleanField(default=False)
    has_international_collaboration = models.BooleanField(default=False)
    publication_medium = models.CharField(max_length=24, choices=PublicationMedium.choices)
    paper_nature = models.CharField(max_length=16, choices=PaperNature.choices)
    paper_attribute = models.CharField(max_length=16, choices=PaperAttribute.choices)
    total_pages = models.PositiveIntegerField(null=True, blank=True)
    is_annual_representative_work = models.BooleanField(default=False)
    is_peer_reviewed = models.BooleanField(default=False)
    citation_count = models.PositiveIntegerField(null=True, blank=True)
    publication_country = models.ForeignKey(Country, on_delete=models.PROTECT, null=True, blank=True, related_name="journal_publications")
    publication_place = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "期刊論文明細"
        verbose_name_plural = "期刊論文明細"

    def clean(self):
        errors = {}
        if self.journal_type in {self.JournalType.SCI, self.JournalType.SSCI}:
            if not self.international_journal_rank:
                errors["international_journal_rank"] = "SCI／SSCI 必須填寫期刊排名。"
        elif self.international_journal_rank or self.impact_factor is not None:
            errors["international_journal_rank"] = "僅 SCI／SSCI 可填寫排名與 Impact factor。"
        if self.journal_type in {self.JournalType.TSSCI, self.JournalType.THCI}:
            if not self.taiwan_journal_level:
                errors["taiwan_journal_level"] = "TSSCI／THCI 必須填寫收錄級別。"
        elif self.taiwan_journal_level:
            errors["taiwan_journal_level"] = "僅 TSSCI／THCI 可填寫收錄級別。"
        if self.journal_type in {self.JournalType.COLLEGE_RECOGNIZED, self.JournalType.OTHER}:
            if not self.custom_journal_type.strip():
                errors["custom_journal_type"] = "請說明期刊類型。"
        elif self.custom_journal_type:
            errors["custom_journal_type"] = "僅各院認可之優良期刊或其他可填寫說明。"
        if self.student_author_order == self.StudentAuthorOrder.FOURTH_OR_LATER and not self.student_author_order_reason.strip():
            errors["student_author_order_reason"] = "第四作者（含）以後必須填寫原因。"
        if errors:
            raise ValidationError(errors)


class ConferenceDetail(models.Model):
    class ConferenceType(models.TextChoices):
        INTERNATIONAL = "international", "國際研討會"
        DOMESTIC = "domestic", "國內研討會"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.OneToOneField(PublicationRecord, on_delete=models.PROTECT, related_name="conference_detail")
    conference_type = models.CharField(max_length=16, choices=ConferenceType.choices)
    organizer = models.CharField(max_length=500)
    location_country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="conference_locations")
    location_city = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    received_subsidy = models.BooleanField(default=False)
    presented_paper = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "學術會議明細"
        verbose_name_plural = "學術會議明細"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "結束日期不得早於起始日期。"})


class ConferenceParticipantCountry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conference = models.ForeignKey(ConferenceDetail, on_delete=models.PROTECT, related_name="participant_country_assignments")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="conference_participations")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conference", "country"], name="uq_conference_participant_country")]
        verbose_name = "會議與會國家"
        verbose_name_plural = "會議與會國家"


class ConferencePresentationMode(models.Model):
    """Stable, manageable mode catalogue; no free-text presentation identity."""
    class Code(models.TextChoices):
        KEYNOTE_SPEAKER = "keynote_speaker", "Keynote speaker"
        INVITED_SPEAKER = "invited_speaker", "Invited speaker"
        SESSION_CHAIRMAN = "session_chairman", "Session chairman"
        ORAL = "oral", "Oral"
        POSTER = "poster", "Poster"
        ABSTRACT = "abstract", "Abstract"
        ARTICLE = "article", "Article"
        ATTENDANCE_ONLY = "attendance_only", "僅與會"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, choices=Code.choices, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "code"]
        verbose_name = "會議發表方式"
        verbose_name_plural = "會議發表方式"

    def __str__(self):
        return self.display_name


class ConferencePresentationModeAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conference = models.ForeignKey(ConferenceDetail, on_delete=models.PROTECT, related_name="presentation_mode_assignments")
    mode = models.ForeignKey(ConferencePresentationMode, on_delete=models.PROTECT, related_name="conference_assignments")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conference", "mode"], name="uq_conference_presentation_mode")]
        verbose_name = "會議發表方式對照"
        verbose_name_plural = "會議發表方式對照"
