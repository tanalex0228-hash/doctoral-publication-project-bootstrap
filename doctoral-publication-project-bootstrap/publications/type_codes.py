"""Stable compatibility aliases for behaviour-bearing publication subtypes.

PublicationType itself remains administrator-managed taxonomy.  These aliases
only connect established taxonomy identifiers to the RC4 detail workflows.
"""

JOURNAL_TYPE_SLUGS = frozenset({"journal", "journal_article"})
CONFERENCE_TYPE_SLUGS = frozenset({"conference", "academic_conference"})


def publication_detail_kind(publication_type):
    if publication_type.slug in JOURNAL_TYPE_SLUGS:
        return "journal"
    if publication_type.slug in CONFERENCE_TYPE_SLUGS:
        return "conference"
    return None
