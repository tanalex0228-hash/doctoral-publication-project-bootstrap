from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from documents.models import SourceDocument
from documents.services import upload_document
from publications.models import ConferencePresentationMode, Country, PublicationRecord
from publications.services import submit_publication
from review.services import approve_publication, return_for_revision
from taxonomy.models import PublicationType
from tests.test_core_contract import ContractFixture


class RC5BusinessUiTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.country, _ = Country.objects.get_or_create(code="TW", defaults={"zh_name": "臺灣"})

    def journal_payload(self, title="RC5 journal"):
        return {
            "type_flow": "1", "publication_type": str(self.type.id), "title": title,
            "language": "zh-Hant", "journal_or_conference_name": "RC5 Journal",
            "publication_stage": PublicationRecord.PublicationStage.PUBLISHED,
            "journal_type": "sci", "international_journal_rank": "top_10",
            "impact_factor": "3.1000", "student_author_order": "first",
            "student_author_attribute": "first_author", "publication_medium": "electronic",
            "paper_nature": "academic", "paper_attribute": "applied",
        }

    def test_dashboard_and_explicit_journal_flow_create_complete_subtype(self):
        self.client.force_login(self.student_user)
        dashboard = self.client.get(reverse("dashboard:student"))
        self.assertContains(dashboard, reverse("publications:journal_create"))
        self.assertContains(dashboard, reverse("publications:conference_create"))
        response = self.client.post(reverse("publications:journal_create"), self.journal_payload())
        self.assertEqual(response.status_code, 302)
        publication = PublicationRecord.objects.get(title="RC5 journal")
        self.assertEqual(publication.journal_detail.journal_type, "sci")
        detail = self.client.get(reverse("publications:detail", args=[publication.id]))
        self.assertContains(detail, "期刊完整明細")
        self.assertContains(detail, "SCI／SSCI 排名與 IF")

    def test_explicit_conference_flow_and_type_specific_edit(self):
        conference_type = PublicationType.objects.create(slug="conference", display_name="學術會議")
        mode, _ = ConferencePresentationMode.objects.get_or_create(code="oral", defaults={"display_name": "Oral"})
        self.client.force_login(self.student_user)
        data = {
            "type_flow": "1", "publication_type": str(conference_type.id), "title": "RC5 conference",
            "language": "zh-Hant", "journal_or_conference_name": "RC5 Meeting",
            "conference_type": "international", "organizer": "Fu Jen", "location_country": str(self.country.id),
            "location_city": "Taipei", "start_date": "2026-01-01", "end_date": "2026-01-02",
            "participant_countries": [str(self.country.id)], "presentation_modes": [str(mode.id)],
        }
        response = self.client.post(reverse("publications:conference_create"), data)
        self.assertEqual(response.status_code, 302)
        publication = PublicationRecord.objects.get(title="RC5 conference")
        self.assertEqual(publication.conference_detail.organizer, "Fu Jen")
        edit = self.client.get(reverse("publications:conference_edit", args=[publication.id]))
        self.assertContains(edit, "會議完整明細")

    def test_withdraw_and_document_version_operations_preserve_history(self):
        publication = self.publication()
        self.client.force_login(self.student_user)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            original = upload_document(
                actor=self.student_user, publication=publication,
                upload=SimpleUploadedFile("original.pdf", b"%PDF-1.4 original", content_type="application/pdf"),
            )
            response = self.client.post(reverse("documents:replace", args=[publication.id, original.id]), {
                "document_type": SourceDocument.DocumentType.OTHER,
                "file": SimpleUploadedFile("new.pdf", b"%PDF-1.4 replacement", content_type="application/pdf"),
            })
            self.assertEqual(response.status_code, 302)
            original.refresh_from_db()
            replacement = SourceDocument.objects.get(supersedes=original)
            self.assertFalse(original.is_active)
            self.assertTrue(replacement.is_active)
            response = self.client.post(reverse("documents:remove", args=[publication.id, replacement.id]))
            self.assertEqual(response.status_code, 302)
            replacement.refresh_from_db()
            self.assertFalse(replacement.is_active)
        response = self.client.post(reverse("publications:withdraw", args=[publication.id]))
        self.assertEqual(response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.WITHDRAWN)

    def test_submitted_review_detail_shows_full_business_context(self):
        publication = self.publication()
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("review:detail", args=[publication.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.student_number)
        self.assertContains(response, "審核與流程歷史")
        return_for_revision(actor=self.staff, publication_id=publication.id, reason="補件")
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse("publications:detail", args=[publication.id])).status_code, 200)
