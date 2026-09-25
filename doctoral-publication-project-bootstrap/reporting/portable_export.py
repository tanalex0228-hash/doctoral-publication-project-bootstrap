"""Deterministic, dependency-free metadata contract for long-term exports."""

from collections import OrderedDict

from accounts.models import Role, User, UserRole
from advising.models import StudentAdvisor
from audit.models import AuditLog
from documents.models import SourceDocument
from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from publications.models import (
    PublicationAuthor,
    PublicationFieldAssignment,
    PublicationIndexAssignment,
    PublicationRecord,
    PublicationSeries,
)
from review.models import PublicationTransition, ReviewDecision
from taxonomy.models import PublicationIndex, PublicationType, ResearchField


EXPORT_MODELS = OrderedDict((
    ("users", User), ("roles", Role), ("user_roles", UserRole),
    ("students", DoctoralStudentProfile), ("professors", Professor),
    ("student_advisors", StudentAdvisor),
    ("publication_types", PublicationType), ("publication_indices", PublicationIndex),
    ("research_fields", ResearchField), ("publication_series", PublicationSeries),
    ("publications", PublicationRecord), ("publication_authors", PublicationAuthor),
    ("publication_index_assignments", PublicationIndexAssignment),
    ("publication_field_assignments", PublicationFieldAssignment),
    ("review_decisions", ReviewDecision), ("publication_transitions", PublicationTransition),
    ("audit_logs", AuditLog),
))


def primitive(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def rows_for(model):
    """Stable, secret-free rows ordered by UUID for CSV/JSON serializers."""
    fields = [field for field in model._meta.concrete_fields if field.name not in {"password"}]
    for object_id in model.objects.order_by("pk").values_list("pk", flat=True):
        obj = model.objects.get(pk=object_id)
        yield {
            field.name: primitive(getattr(obj, field.attname if field.is_relation else field.name))
            for field in fields
        }


def document_manifest():
    """Private storage keys are exported only as an operator-only file manifest."""
    return [
        {
            "id": str(document.id),
            "publication_id": str(document.publication_id),
            "storage_key": document.storage_key,
            "original_filename": document.original_filename,
            "checksum_sha256": document.checksum_sha256,
            "file_size": document.file_size,
            "is_active": document.is_active,
        }
        for document in SourceDocument.objects.order_by("pk")
    ]
