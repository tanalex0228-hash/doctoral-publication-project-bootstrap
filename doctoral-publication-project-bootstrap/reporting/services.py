from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Count, F, Max, Min, Q
from doctoral_students.models import DoctoralStudentProfile
from publications.models import PublicationRecord
from publications.querysets import official_publications


def approved_publications():
    """Compatibility name for the single valid-official-results contract."""
    return official_publications()


def filtered_approved_publications(*, student=None, year=None, publication_type=None,
                                   publication_index=None, research_field=None, advisor=None,
                                   language=None, author_role=None, date_basis="publication_date",
                                   date_from=None, date_to=None):
    """Apply administrative statistics filters to the approved-only universe."""
    records = approved_publications()
    if student:
        records = records.filter(owner_student=student)
    if year:
        records = records.filter(publication_date__year=year)
    if publication_type:
        records = records.filter(publication_type=publication_type)
    if publication_index:
        records = records.filter(indices=publication_index)
    if research_field:
        records = records.filter(research_fields=research_field)
    if advisor:
        records = records.filter(
            owner_student__advisor_relations__professor=advisor,
            owner_student__advisor_relations__is_active=True,
        )
    if language:
        records = records.filter(language=language)
    if author_role == "first_author":
        records = records.filter(authors__author_order=1, authors__linked_user=F("owner_student__user"))
    elif author_role == "corresponding_author":
        records = records.filter(authors__is_corresponding_author=True, authors__linked_user=F("owner_student__user"))
    date_field = "accepted_date" if date_basis == "accepted_date" else "publication_date"
    if date_from:
        records = records.filter(**{f"{date_field}__gte": date_from})
    if date_to:
        records = records.filter(**{f"{date_field}__lte": date_to})
    return records.distinct()


def statistics_overview(records):
    """Return approved-only aggregate data for the secretary dashboard."""
    return {
        "approved_total": records.count(),
        "student_total": records.values("owner_student_id").distinct().count(),
        "publication_types": records.values("publication_type__display_name").annotate(
            total=Count("pk", distinct=True)
        ).order_by("publication_type__display_name"),
        "publication_indices": records.filter(indices__isnull=False).values("indices__display_name").annotate(
            total=Count("pk", distinct=True)
        ).order_by("indices__display_name"),
        "years": records.filter(publication_date__isnull=False).values("publication_date__year").annotate(
            total=Count("pk", distinct=True)
        ).order_by("-publication_date__year"),
        "research_fields": records.filter(research_fields__isnull=False).values("research_fields__display_name").annotate(
            total=Count("pk", distinct=True)
        ).order_by("research_fields__display_name"),
    }


def student_summary(student):
    records = approved_publications().filter(owner_student=student)
    author_records = records.filter(authors__linked_user=student.user)
    return {
        "approved_total": records.count(),
        "journal_total": records.filter(publication_type__slug="journal").count(),
        "conference_total": records.filter(publication_type__slug="conference").count(),
        "first_author_total": author_records.filter(authors__author_order=1).distinct().count(),
        "corresponding_author_total": author_records.filter(authors__is_corresponding_author=True).distinct().count(),
        "advisor_coauthored_total": records.filter(
            authors__linked_professor__student_relations__student=student,
            authors__linked_professor__student_relations__is_active=True,
        ).distinct().count(),
        "publication_index_counts": records.filter(indices__isnull=False).values(
            "indices__display_name"
        ).annotate(total=Count("pk", distinct=True)).order_by("indices__display_name"),
        "yearly_publications": records.filter(publication_date__isnull=False).values(
            "publication_date__year"
        ).annotate(total=Count("pk", distinct=True)).order_by("-publication_date__year"),
        "latest_approved_at": records.aggregate(value=Max("approved_at"))["value"],
    }


def staff_table():
    return student_statistics_table(approved_publications())


STUDENT_SORTS = {
    "name": ("display_name", "student_number"),
    "approved_count": ("-approved_total", "display_name"),
    "publication_date": ("-latest_publication_date", "display_name"),
    "publication_type": ("first_publication_type", "display_name"),
    "advisor": ("advisor_names", "display_name"),
}


def student_statistics_table(records, sort="name"):
    """Create a filtered, approved-only student statistics read model."""
    record_filter = Q(publications__in=records)
    students = DoctoralStudentProfile.objects.filter(publications__in=records).annotate(
        approved_total=Count("publications", filter=record_filter, distinct=True),
        journal_total=Count(
            "publications",
            filter=record_filter & Q(publications__publication_type__slug="journal"),
            distinct=True,
        ),
        conference_total=Count(
            "publications",
            filter=record_filter & Q(publications__publication_type__slug="conference"),
            distinct=True,
        ),
        first_author_total=Count(
            "publications",
            filter=record_filter & Q(publications__authors__author_order=1, publications__authors__linked_user=F("user")),
            distinct=True,
        ),
        corresponding_author_total=Count(
            "publications",
            filter=record_filter & Q(publications__authors__is_corresponding_author=True, publications__authors__linked_user=F("user")),
            distinct=True,
        ),
        advisor_coauthored_total=Count(
            "publications",
            filter=record_filter & Q(
                publications__authors__linked_professor=F("advisor_relations__professor"),
                advisor_relations__is_active=True,
            ),
            distinct=True,
        ),
        publication_index_summary=StringAgg(
            "publications__indices__display_name",
            delimiter="、",
            distinct=True,
            filter=record_filter & Q(publications__indices__isnull=False),
        ),
        advisor_names=StringAgg(
            "advisor_relations__professor__display_name",
            delimiter="、",
            distinct=True,
            filter=Q(advisor_relations__is_active=True),
        ),
        latest_approved_at=Max("publications__approved_at", filter=record_filter),
        latest_publication_date=Max("publications__publication_date", filter=record_filter),
        first_publication_type=Min("publications__publication_type__display_name", filter=record_filter),
    ).distinct()
    return students.order_by(*STUDENT_SORTS.get(sort, STUDENT_SORTS["name"]))


def approved_publications_for_student(student):
    """Approved-only drill-down queryset with related metadata for staff views."""
    return approved_publications().filter(owner_student=student).select_related(
        "owner_student", "publication_type"
    ).prefetch_related(
        "authors",
        "indices",
        "research_fields",
        "owner_student__advisor_relations__professor",
    ).order_by("-publication_date", "-approved_at", "title")


def export_ready_publications(records):
    """Return a presentation-ready queryset, not an export file or new format."""
    return records.select_related("owner_student", "publication_type").prefetch_related(
        "authors",
        "indices",
        "research_fields",
        "owner_student__advisor_relations__professor",
    ).order_by("owner_student__student_number", "-publication_date", "title")


def export_ready_rows(records):
    """Flatten the existing approved-only export queryset for CSV delivery."""
    for publication in export_ready_publications(records):
        advisors = "、".join(
            relation.professor.display_name
            for relation in publication.owner_student.advisor_relations.all()
            if relation.is_active
        )
        yield [
            publication.owner_student.display_name,
            publication.owner_student.student_number,
            advisors,
            publication.title,
            publication.publication_type.display_name,
            "、".join(index.display_name for index in publication.indices.all()),
            "、".join(field.display_name for field in publication.research_fields.all()),
            "、".join(author.display_name for author in publication.authors.all()),
            publication.journal_or_conference_name,
            publication.publication_date.isoformat() if publication.publication_date else "",
            publication.accepted_date.isoformat() if publication.accepted_date else "",
            publication.doi or "",
            publication.issn or "",
            publication.language,
            publication.approved_at.isoformat() if publication.approved_at else "",
            publication.get_visibility_scope_display(),
            "已發佈" if publication.is_published else "未發佈",
        ]


def csv_safe_cell(value):
    value = "" if value is None else str(value)
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value
