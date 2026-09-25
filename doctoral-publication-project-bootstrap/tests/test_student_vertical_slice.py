from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from pathlib import Path
from tempfile import TemporaryDirectory
from documents.models import SourceDocument
from publications.models import PublicationAuthor, PublicationRecord
from publications.services import create_publication, submit_publication
from review.services import return_for_revision
from tests.test_core_contract import ContractFixture


class StudentVerticalSliceTests(ContractFixture):
    def payload(self, title="My publication"):
        return {
            "publication_type": str(self.type.id), "title": title, "language": "en",
            "publication_stage": PublicationRecord.PublicationStage.PUBLISHED,
            "journal_or_conference_name": "Journal of Tests", "indices": [], "research_fields": [],
        }

    def test_dashboard_and_detail_never_expose_another_students_private_publication(self):
        mine = self.publication()
        other = create_publication(actor=self.other_student_user, owner_student=self.other_student, publication_type=self.type, title="Student B private record")
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("dashboard:student"))
        self.assertContains(response, mine.title)
        self.assertNotContains(response, other.title)
        self.assertEqual(self.client.get(reverse("publications:detail", args=[other.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse("publications:edit", args=[other.id])).status_code, 404)

    def test_student_can_use_regular_login_without_admin_access(self):
        response = self.client.post(reverse("accounts:login"), {"username": "student", "password": "pass"})
        self.assertRedirects(response, reverse("dashboard:student"))

    def test_draft_can_be_created_and_edited_by_owner(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("publications:create"), self.payload("Initial title"))
        self.assertEqual(response.status_code, 302)
        publication = PublicationRecord.objects.get(title="Initial title")
        self.assertEqual(publication.owner_student, self.student)
        response = self.client.post(reverse("publications:edit", args=[publication.id]), self.payload("Updated title"))
        self.assertEqual(response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.title, "Updated title")
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.DRAFT)

    def test_submitted_cannot_be_edited_by_student(self):
        publication = self.publication()
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("publications:edit", args=[publication.id]), self.payload("Forbidden edit"))
        self.assertEqual(response.status_code, 404)
        publication.refresh_from_db()
        self.assertNotEqual(publication.title, "Forbidden edit")

    def test_submit_runs_completeness_validation_before_workflow_transition(self):
        publication = self.publication()
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("publications:submit", args=[publication.id]), follow=True)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.DRAFT)
        self.assertContains(response, "請至少新增一位作者")
        self.assertContains(response, "請至少上傳一份有效佐證文件")

    def test_returned_can_be_edited_and_resubmitted(self):
        publication = self.publication()
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        return_for_revision(actor=self.staff, publication_id=publication.id, reason="Clarify title")
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("publications:edit", args=[publication.id]), self.payload("Clarified title"))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse("publications:submit", args=[publication.id]))
        self.assertEqual(response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.title, "Clarified title")
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.SUBMITTED)

    def test_author_crud_and_ordering_stay_inside_owned_editable_publication(self):
        publication = self.publication()
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("publications:author_create", args=[publication.id]), {"display_name": "First author", "affiliation": "Fu Jen"})
        self.assertEqual(response.status_code, 302)
        first = publication.authors.get(display_name="First author")
        self.client.post(reverse("publications:author_create", args=[publication.id]), {"display_name": "Second author", "affiliation": "External"})
        second = publication.authors.get(display_name="Second author")
        self.client.post(reverse("publications:author_move", args=[publication.id, second.id, "up"]))
        second.refresh_from_db(); first.refresh_from_db()
        self.assertEqual((second.author_order, first.author_order), (1, 2))
        self.client.post(reverse("publications:author_edit", args=[publication.id, second.id]), {"display_name": "Updated author", "affiliation": "External", "is_corresponding_author": "on"})
        second.refresh_from_db()
        self.assertTrue(second.is_corresponding_author)
        self.client.post(reverse("publications:author_delete", args=[publication.id, first.id]))
        self.assertFalse(PublicationAuthor.objects.filter(pk=first.id).exists())

    def test_document_requires_parent_publication_and_download_is_owner_scoped(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SourceDocument.objects.create(document_type="other", original_filename="orphan.pdf", storage_key="orphan", mime_type="application/pdf", file_size=1, checksum_sha256="b" * 64, uploaded_by=self.student_user)
        publication = self.publication()
        document = SourceDocument.objects.create(publication=publication, document_type="other", original_filename="private.pdf", storage_key="missing-file", mime_type="application/pdf", file_size=1, checksum_sha256="c" * 64, uploaded_by=self.student_user)
        self.client.force_login(self.other_student_user)
        self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)

    def test_document_upload_view_uses_private_document_service(self):
        publication = self.publication()
        self.client.force_login(self.student_user)
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                response = self.client.post(reverse("documents:upload", args=[publication.id]), {
                    "document_type": "article_fulltext",
                    "file": SimpleUploadedFile("proof.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                })
                self.assertEqual(response.status_code, 302)
                document = SourceDocument.objects.get(publication=publication)
                self.assertTrue(document.storage_key.startswith("evidence/"))
                self.assertFalse((Path(directory) / "media" / document.storage_key).exists())

    def test_submit_view_calls_existing_workflow_service_and_does_not_expose_approval(self):
        publication = self.publication()
        self.client.force_login(self.student_user)
        with patch("publications.views.submit_publication") as submit:
            response = self.client.post(reverse("publications:submit", args=[publication.id]))
        self.assertEqual(response.status_code, 302)
        submit.assert_called_once_with(actor=self.student_user, publication_id=publication.id)
        with self.assertRaises(PermissionDenied):
            from review.services import approve_publication
            approve_publication(actor=self.student_user, publication_id=publication.id)
