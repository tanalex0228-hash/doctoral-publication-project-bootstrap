from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from documents.models import SourceDocument
from documents.services import upload_document
from publications.models import (
    ConferencePresentationMode, Country, JournalArticleDetail,
    SustainableDevelopmentGoal, PublicationRecord,
)
from publications.services import (
    create_revision, save_conference_detail, save_journal_article_detail,
    set_publication_sdgs,
)
from reporting.secretary_exports import CONFERENCE_HEADERS, JOURNAL_HEADERS, conference_rows, journal_rows
from review.services import approve_publication
from tests.test_core_contract import ContractFixture
from taxonomy.models import PublicationType


class SecretaryFormalFieldTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.taiwan = Country.objects.get(code="0")
        self.japan = Country.objects.get(code="13")
        self.singapore = Country.objects.get(code="27")

    def journal_values(self, **overrides):
        values = {
            "journal_type": JournalArticleDetail.JournalType.SCI,
            "international_journal_rank": JournalArticleDetail.InternationalJournalRank.TOP_25_50,
            "impact_factor": "2.5000",
            "student_author_order": JournalArticleDetail.StudentAuthorOrder.FIRST,
            "student_author_attribute": JournalArticleDetail.StudentAuthorAttribute.FIRST_AUTHOR,
            "publication_medium": JournalArticleDetail.PublicationMedium.ELECTRONIC,
            "paper_nature": JournalArticleDetail.PaperNature.ACADEMIC,
            "paper_attribute": JournalArticleDetail.PaperAttribute.APPLIED,
        }
        values.update(overrides)
        return values

    def test_journal_detail_requires_only_its_applicable_conditional_values(self):
        publication = self.publication()
        detail = save_journal_article_detail(
            actor=self.student_user, publication_id=publication.id, **self.journal_values()
        )
        self.assertEqual(detail.journal_type, "sci")
        with self.assertRaises(ValidationError):
            save_journal_article_detail(
                actor=self.student_user, publication_id=publication.id,
                **self.journal_values(
                    journal_type=JournalArticleDetail.JournalType.TSSCI,
                    international_journal_rank="",
                    impact_factor=None,
                    taiwan_journal_level="",
                ),
            )
        with self.assertRaises(ValidationError):
            save_journal_article_detail(
                actor=self.student_user, publication_id=publication.id,
                **self.journal_values(
                    student_author_order=JournalArticleDetail.StudentAuthorOrder.FOURTH_OR_LATER,
                    student_author_order_reason="",
                ),
            )

    def test_sdg_limit_and_none_exclusivity_are_service_enforced(self):
        publication = self.publication()
        goals = list(SustainableDevelopmentGoal.objects.exclude(code="NONE").order_by("code"))
        with self.assertRaises(ValidationError):
            set_publication_sdgs(actor=self.student_user, publication_id=publication.id, goals=goals[:4])
        with self.assertRaises(ValidationError):
            set_publication_sdgs(
                actor=self.student_user, publication_id=publication.id,
                goals=[SustainableDevelopmentGoal.objects.get(code="NONE"), goals[0]],
            )
        set_publication_sdgs(actor=self.student_user, publication_id=publication.id, goals=goals[:3])
        self.assertEqual(publication.sdg_assignments.count(), 3)

    def test_conference_countries_have_a_five_country_limit_and_modes_are_relational(self):
        publication = self.publication()
        countries = [self.taiwan, self.japan, self.singapore]
        # Additional controlled records make the boundary independent of the
        # currently supplied historical country subset.
        for code in ("X1", "X2", "X3"):
            countries.append(Country.objects.create(code=code, zh_name=code))
        with self.assertRaises(ValidationError):
            save_conference_detail(
                actor=self.student_user, publication_id=publication.id,
                conference_type="international", organizer="Fu Jen", location_country=self.taiwan,
                location_city="Taipei", start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
                participant_countries=countries, presentation_modes=[],
            )
        modes = list(ConferencePresentationMode.objects.filter(code__in=["oral", "attendance_only"]))
        detail = save_conference_detail(
            actor=self.student_user, publication_id=publication.id,
            conference_type="international", organizer="Fu Jen", location_country=self.taiwan,
            location_city="Taipei", start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            participant_countries=countries[:3], presentation_modes=modes,
        )
        self.assertEqual(detail.participant_country_assignments.count(), 3)
        self.assertEqual(detail.presentation_mode_assignments.count(), 2)

    def test_revision_copies_detail_and_normalized_assignments(self):
        publication = self.publication()
        detail = save_conference_detail(
            actor=self.student_user, publication_id=publication.id,
            conference_type="domestic", organizer="Fu Jen", location_country=self.taiwan,
            location_city="Taipei", start_date=date(2026, 1, 1), end_date=date(2026, 1, 1),
            participant_countries=[self.taiwan, self.japan],
            presentation_modes=[ConferencePresentationMode.objects.get(code="oral")],
        )
        set_publication_sdgs(
            actor=self.student_user, publication_id=publication.id,
            goals=[SustainableDevelopmentGoal.objects.get(code="SDG03")],
        )
        # A revision is permitted only for an official version.  Complete the
        # frozen workflow using its established services.
        self.complete(publication)
        from publications.services import submit_publication
        from review.services import approve_publication
        submit_publication(actor=self.student_user, publication_id=publication.id)
        approve_publication(actor=self.staff, publication_id=publication.id)
        revision = create_revision(actor=self.student_user, publication_id=publication.id)
        self.assertEqual(revision.conference_detail.organizer, detail.organizer)
        self.assertEqual(revision.conference_detail.participant_country_assignments.count(), 2)
        self.assertEqual(revision.conference_detail.presentation_mode_assignments.count(), 1)
        self.assertEqual(revision.sdg_assignments.count(), 1)

    def test_conference_evidence_is_private_pdf_and_limited_to_ten_mb(self):
        publication = self.publication()
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            document = upload_document(
                actor=self.student_user, publication=publication,
                document_type=SourceDocument.DocumentType.CONFERENCE_EVIDENCE,
                upload=SimpleUploadedFile("conference.pdf", b"%PDF-1.4 evidence", content_type="application/pdf"),
            )
            self.assertEqual(document.document_type, SourceDocument.DocumentType.CONFERENCE_EVIDENCE)
            with self.assertRaises(ValidationError):
                upload_document(
                    actor=self.student_user, publication=publication,
                    document_type=SourceDocument.DocumentType.CONFERENCE_EVIDENCE,
                    upload=SimpleUploadedFile("conference.png", b"\x89PNG\r\n\x1a\nimage", content_type="image/png"),
                )

    def test_journal_submission_checks_accepted_and_published_evidence_requirements(self):
        from publications.services import submit_publication
        accepted = self.publication()
        accepted.publication_stage = accepted.PublicationStage.ACCEPTED
        accepted.save(update_fields=["publication_stage"])
        save_journal_article_detail(actor=self.student_user, publication_id=accepted.id, **self.journal_values())
        self.complete(accepted)
        with self.assertRaises(ValidationError) as error:
            submit_publication(actor=self.student_user, publication_id=accepted.id)
        self.assertIn("接受日期", error.exception.messages[0])
        accepted.accepted_date = date(2026, 1, 1)
        accepted.save(update_fields=["accepted_date"])
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            upload_document(
                actor=self.student_user, publication=accepted,
                document_type=SourceDocument.DocumentType.ACCEPTANCE_LETTER,
                upload=SimpleUploadedFile("accepted.pdf", b"%PDF-1.4 accepted", content_type="application/pdf"),
            )
        submit_publication(actor=self.student_user, publication_id=accepted.id)

        published = self.publication()
        save_journal_article_detail(actor=self.student_user, publication_id=published.id, **self.journal_values())
        self.complete(published)
        with self.assertRaises(ValidationError) as error:
            submit_publication(actor=self.student_user, publication_id=published.id)
        self.assertIn("卷號", error.exception.messages[0])

    def test_detail_pages_are_owner_editable_and_keep_other_students_out(self):
        publication = self.publication()
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse("publications:journal_detail_edit", args=[publication.id])).status_code, 200)
        self.client.force_login(self.other_student_user)
        self.assertEqual(self.client.get(reverse("publications:journal_detail_edit", args=[publication.id])).status_code, 404)

    def test_secretary_exports_keep_legacy_headers_and_only_official_records(self):
        journal = self.publication()
        journal.volume, journal.issue, journal.pages_or_article_number, journal.publication_date = "1", "2", "1-10", date(2026, 1, 1)
        journal.save(update_fields=["volume", "issue", "pages_or_article_number", "publication_date"])
        save_journal_article_detail(actor=self.student_user, publication_id=journal.id, **self.journal_values())
        self.complete(journal)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            upload_document(
                actor=self.student_user, publication=journal,
                document_type=SourceDocument.DocumentType.JOURNAL_PROOF,
                upload=SimpleUploadedFile("journal.pdf", b"%PDF-1.4 journal", content_type="application/pdf"),
            )
        from publications.services import submit_publication
        submit_publication(actor=self.student_user, publication_id=journal.id)
        approve_publication(actor=self.staff, publication_id=journal.id)
        self.assertEqual(len(JOURNAL_HEADERS), 36)
        self.assertEqual(len(CONFERENCE_HEADERS), 29)
        rows = list(journal_rows())
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), len(JOURNAL_HEADERS))
        self.assertEqual(list(conference_rows()), [])
        self.client.force_login(self.staff)
        response = self.client.get(reverse("statistics:secretary_journal_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("期刊類型(新)".encode(), response.content)

    def test_journal_article_taxonomy_slug_opens_full_journal_create_flow(self):
        self.type.slug = "journal_article"
        self.type.save(update_fields=["slug"])
        self.client.force_login(self.student_user)
        selection = self.client.get(reverse("publications:create"))
        self.assertContains(selection, "請先選擇成果類型")
        response = self.client.get(reverse("publications:create"), {"publication_type": self.type.id})
        self.assertContains(response, "期刊論文正式欄位")
        self.assertContains(response, "學生作者序")
        data = {
            "type_flow": "1", "publication_type": str(self.type.id), "title": "RC4 journal create",
            "language": "zh-Hant", "publication_stage": PublicationRecord.PublicationStage.PUBLISHED,
            "journal_or_conference_name": "Journal of RC4", "journal_type": "sci",
            "international_journal_rank": "top_10", "impact_factor": "1.2500",
            "student_author_order": "first", "student_author_attribute": "first_author",
            "publication_medium": "electronic", "paper_nature": "academic", "paper_attribute": "applied",
        }
        response = self.client.post(reverse("publications:create"), data)
        self.assertEqual(response.status_code, 302)
        publication = PublicationRecord.objects.get(title="RC4 journal create")
        self.assertEqual(publication.journal_detail.journal_type, "sci")

    def test_conference_taxonomy_slug_opens_conference_create_flow(self):
        conference_type = PublicationType.objects.create(slug="conference", display_name="學術會議")
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("publications:create"), {"publication_type": conference_type.id})
        self.assertContains(response, "學術會議與發表正式欄位")
        self.assertContains(response, "與會人員國家")
        self.assertNotContains(response, "卷號")
