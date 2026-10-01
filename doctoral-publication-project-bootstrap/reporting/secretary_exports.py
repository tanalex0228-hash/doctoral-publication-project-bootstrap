"""Secretary CSV contracts aligned to the supplied legacy export headers.

Only valid official publications are exported.  The old export's `完成` value
is intentionally not manufactured from, or mapped to, lifecycle status.
"""

from publications.querysets import official_publications


JOURNAL_HEADERS = [
    "教師", "教師代碼", "所屬單位", "學院", "狀態", "論文篇名", "期刊名", "作者", "發表進度",
    "接受日期", "刊登日期", "卷號", "期別", "頁數", "期刊類型(舊)", "期刊類型(新)",
    "SCI、SSCI國際學術期刊排名", "收錄期刊之Impact factor", "臺灣人文及社會科學期刊評比暨核心期刊收錄級別",
    "作者序", "作者屬性", "通訊作者", "國際合作", "年度代表作", "審查機制", "出版媒體", "論文性質",
    "論文屬性", "國際標準期刊號ISSN", "引用次數", "總頁數", "出版國", "出版地", "資料建立時間", "備註", "SDGs",
]

CONFERENCE_HEADERS = [
    "教師", "教師代碼", "所屬單位", "學院", "狀態", "學術會議名", "會議屬性", "主辦單位", "會議地點國家",
    "會議地點城市", "與會人員國家", "起始日期", "結束日期", "發表方式或任務", "是否發表論文", "論文篇名",
    "作者", "通訊作者", "作者序", "論文性質", "論文屬性", "論文是否有審查機制", "頁數", "國際合作",
    "國際合作類型", "SCOPUS收錄", "資料建立時間", "備註", "SDGs",
]


def _yes_no(value):
    return "是" if value else "否"


def _date(value):
    return value.isoformat() if value else ""


def _student_columns(publication):
    student = publication.owner_student
    # The current doctoral profile owns identity; legacy organisation columns
    # have no canonical source in Architecture Freeze v1 and remain blank.
    return [student.display_name, student.student_number, "", ""]


def _sdgs(publication):
    return ", ".join(assignment.goal.display_name for assignment in publication.sdg_assignments.all())


def _official_for_type(slug, detail_relation):
    return official_publications().filter(publication_type__slug=slug).select_related(
        "owner_student", "publication_type", detail_relation,
    ).prefetch_related(
        "authors", "sdg_assignments__goal",
        f"{detail_relation}__participant_country_assignments__country",
        f"{detail_relation}__presentation_mode_assignments__mode",
    ).order_by("owner_student__student_number", "title")


def journal_rows():
    records = official_publications().filter(publication_type__slug="journal").select_related(
        "owner_student", "journal_detail__publication_country",
    ).prefetch_related("authors", "sdg_assignments__goal").order_by("owner_student__student_number", "title")
    for publication in records:
        try:
            detail = publication.journal_detail
        except Exception:  # Legacy official rows may not yet be reconciled.
            detail = None
        yield _student_columns(publication) + [
            "", publication.title, publication.journal_or_conference_name,
            ", ".join(author.display_name for author in publication.authors.all()), publication.get_publication_stage_display(),
            _date(publication.accepted_date), _date(publication.publication_date), publication.volume, publication.issue,
            publication.pages_or_article_number,
            detail.legacy_journal_type if detail else "", detail.get_journal_type_display() if detail else "",
            detail.get_international_journal_rank_display() if detail and detail.international_journal_rank else "",
            detail.impact_factor if detail and detail.impact_factor is not None else "",
            detail.get_taiwan_journal_level_display() if detail and detail.taiwan_journal_level else "",
            detail.get_student_author_order_display() if detail else "", detail.get_student_author_attribute_display() if detail else "",
            _yes_no(detail.is_student_corresponding_author) if detail else "", _yes_no(detail.has_international_collaboration) if detail else "",
            _yes_no(detail.is_annual_representative_work) if detail else "", _yes_no(detail.is_peer_reviewed) if detail else "",
            detail.get_publication_medium_display() if detail else "", detail.get_paper_nature_display() if detail else "",
            detail.get_paper_attribute_display() if detail else "", publication.issn or "", detail.citation_count if detail and detail.citation_count is not None else "",
            detail.total_pages if detail and detail.total_pages is not None else "",
            str(detail.publication_country) if detail and detail.publication_country else "", detail.publication_place if detail else "",
            publication.created_at.isoformat(), detail.remarks if detail else "", _sdgs(publication),
        ]


def conference_rows():
    records = _official_for_type("conference", "conference_detail")
    for publication in records:
        try:
            detail = publication.conference_detail
        except Exception:  # Legacy official rows may not yet be reconciled.
            detail = None
        countries = "、".join(str(item.country) for item in detail.participant_country_assignments.all()) if detail else ""
        modes = ", ".join(item.mode.display_name for item in detail.presentation_mode_assignments.all()) if detail else ""
        yield _student_columns(publication) + [
            "", publication.journal_or_conference_name,
            detail.get_conference_type_display() if detail else "", detail.organizer if detail else "",
            str(detail.location_country) if detail else "", detail.location_city if detail else "", countries,
            _date(detail.start_date) if detail else "", _date(detail.end_date) if detail else "", modes,
            _yes_no(detail.presented_paper) if detail else "", publication.title,
            ", ".join(author.display_name for author in publication.authors.all()), "", "", "", "", "", "", "", "", "",
            publication.created_at.isoformat(), detail.remarks if detail else "", _sdgs(publication),
        ]
