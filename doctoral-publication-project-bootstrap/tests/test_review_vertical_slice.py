from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.models import User
from advising.models import StudentAdvisor
from audit.models import AuditLog
from documents.services import upload_document
from professors.models import Professor
from publications.models import PublicationRecord
from publications.permissions import can_view_publication
from publications.services import submit_publication
from reporting.services import approved_publications
from tests.test_core_contract import ContractFixture


class ReviewVerticalSliceTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.advisor_user = self.user("advisor-review", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="Advisor Review")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor)
        self.is_staff_only = User.objects.create_user(username="django-staff-only", email="django-staff-only@example.edu", password="pass", is_staff=True)

    def submitted_publication(self, title="Submitted for review"):
        publication = self.publication()
        publication.title = title
        publication.save()
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        return publication

    def test_student_advisor_and_django_is_staff_cannot_access_queue(self):
        for user in (self.student_user, self.advisor_user, self.is_staff_only):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("review:queue")).status_code, 404)

    def test_staff_queue_shows_only_submitted_records_and_supports_filtering(self):
        submitted = self.submitted_publication("Queue target")
        draft = self.publication()
        draft.title = "Draft excluded"
        draft.save()
        self.client.force_login(self.staff)
        response = self.client.get(reverse("review:queue"))
        self.assertContains(response, submitted.title)
        self.assertNotContains(response, draft.title)
        response = self.client.get(reverse("review:queue"), {"q": "Queue target", "sort": "title"})
        self.assertContains(response, submitted.title)

    def test_staff_can_approve_through_review_service_without_auto_publication(self):
        publication = self.submitted_publication()
        self.client.force_login(self.staff)
        response = self.client.post(reverse("review:approve", args=[publication.id]))
        self.assertEqual(response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.APPROVED)
        self.assertFalse(publication.is_published)
        self.assertEqual(publication.visibility_scope, PublicationRecord.VisibilityScope.OWNER_ADVISOR)
        self.assertEqual(approved_publications().filter(pk=publication.id).count(), 1)
        self.assertEqual(publication.review_decisions.filter(action="approve").count(), 1)
        self.assertEqual(publication.transitions.filter(to_status="approved").count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="publication.approved", target_id=publication.id).exists())

    def test_approve_view_calls_existing_review_service(self):
        publication = self.submitted_publication()
        self.client.force_login(self.staff)
        with patch("review.views.approve_publication") as approve:
            response = self.client.post(reverse("review:approve", args=[publication.id]))
        self.assertEqual(response.status_code, 302)
        approve.assert_called_once_with(actor=self.staff, publication_id=publication.id)

    def test_staff_can_return_with_reason_or_without_reason(self):
        first = self.submitted_publication("Needs revision")
        second = self.submitted_publication("No reason needed")
        self.client.force_login(self.staff)
        self.client.post(reverse("review:return_publication", args=[first.id]), {"reason": "Please clarify the DOI."})
        self.client.post(reverse("review:return_publication", args=[second.id]), {"reason": ""})
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(first.workflow_status, PublicationRecord.WorkflowStatus.RETURNED)
        self.assertEqual(second.workflow_status, PublicationRecord.WorkflowStatus.RETURNED)
        self.assertEqual(first.review_decisions.get(action="return").reason, "Please clarify the DOI.")
        self.assertEqual(second.review_decisions.get(action="return").reason, "")
        self.assertFalse(approved_publications().filter(pk__in=[first.id, second.id]).exists())

    def test_advisor_cannot_approve_or_return_even_for_advised_student(self):
        publication = self.submitted_publication()
        self.client.force_login(self.advisor_user)
        self.assertEqual(self.client.post(reverse("review:approve", args=[publication.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("review:return_publication", args=[publication.id]), {"reason": "No"}).status_code, 404)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.SUBMITTED)

    def test_staff_can_configure_visibility_and_publication_independently(self):
        publication = self.submitted_publication()
        self.client.force_login(self.staff)
        self.client.post(reverse("review:approve", args=[publication.id]))
        response = self.client.post(reverse("review:settings", args=[publication.id]), {"visibility_scope": "public"})
        self.assertEqual(response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.APPROVED)
        self.assertEqual(publication.visibility_scope, PublicationRecord.VisibilityScope.PUBLIC)
        self.assertFalse(publication.is_published)
        self.assertFalse(can_view_publication(None, publication))
        self.client.post(reverse("review:settings", args=[publication.id]), {"visibility_scope": "public", "is_published": "on"})
        publication.refresh_from_db()
        self.assertTrue(publication.is_published)
        self.assertTrue(can_view_publication(None, publication))
        self.assertTrue(AuditLog.objects.filter(action="publication.visibility_changed", target_id=publication.id).exists())
        self.assertTrue(AuditLog.objects.filter(action="publication.publish_changed", target_id=publication.id).exists())

    def test_staff_review_detail_uses_permission_checked_private_download(self):
        publication = self.publication()
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                document = upload_document(actor=self.student_user, publication=publication, upload=SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 evidence", content_type="application/pdf"))
                self.complete(publication)
                submit_publication(actor=self.student_user, publication_id=publication.id)
                self.client.force_login(self.staff)
                detail = self.client.get(reverse("review:detail", args=[publication.id]))
                self.assertContains(detail, document.original_filename)
                download = self.client.get(reverse("documents:download", args=[document.id]))
                self.assertEqual(download.status_code, 200)
                self.client.force_login(self.other_student_user)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)
