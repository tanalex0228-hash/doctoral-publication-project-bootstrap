from django.db.models import Q


PORTAL_SORTS = {
    "publication_date": ("-publication_date", "title"),
    "title": ("title",),
    "publication_type": ("publication_type__display_order", "publication_type__display_name", "title"),
}


def portal_publications(queryset, *, q="", year=None, publication_type=None,
                        publication_index=None, research_field=None, language=None,
                        sort="publication_date"):
    """Filter and sort a queryset that has already passed visibility gates."""
    if year:
        queryset = queryset.filter(publication_date__year=year)
    if publication_type:
        queryset = queryset.filter(publication_type=publication_type)
    if publication_index:
        queryset = queryset.filter(indices=publication_index)
    if research_field:
        queryset = queryset.filter(research_fields=research_field)
    if language:
        queryset = queryset.filter(language=language)
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(authors__display_name__icontains=q)
            | Q(journal_or_conference_name__icontains=q)
            | Q(doi__icontains=q)
        )
    return queryset.select_related("publication_type").prefetch_related(
        "authors", "indices", "research_fields"
    ).distinct().order_by(*PORTAL_SORTS.get(sort, PORTAL_SORTS["publication_date"]))
