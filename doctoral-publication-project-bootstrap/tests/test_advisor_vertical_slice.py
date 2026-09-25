from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from accounts.models import UserRole
from advising.models import StudentAdvisor
from documents.services import upload_document
from professors.models import Professor
from publications.models import PublicationRecord
from publications.services import create_publication, submit_publication
from tests.test_core_contract import ContractFixture


class AdvisorVerticalSliceTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.advisor_a_user = self.user("advisor-a", self.advisor_role)
        self.advisor_b_user = self.user("advisor-b", self.advisor_role)
        self.advisor_a = Professor.objects.create(user=self.advisor_a_user, display_name="Advisor A")
        self.advisor_b = Professor.objects.create(user=self.advisor_b_user, display_name="Advisor B")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor_a)
        StudentAdvisor.objects.create(student=self.other_student, professor=self.advisor_b)
        self.own_publication = self.publication()
        self.own_publication.title = "Advisor A visible record"
        self.own_publication.save()
        self.other_publication = create_publication(
            actor=self.other_student_user,
            owner_student=self.other_student,
            publication_type=self.type,
            title="Advisor B private record",
        )

    def test_advisor_sees_only_own_active_advisees_and_login_targets_dashboard(self):
        self.client.force_login(self.advisor_a_user)
        response = self.client.get(reverse("dashboard:advisor"))
        self.assertContains(response, self.student.display_name)
        self.assertNotContains(response, self.other_student.display_name)
        response = self.client.post(reverse("accounts:login"), {"username": "advisor-a", "password": "pass"})
        self.assertRedirects(response, reverse("dashboard:advisor"))

    def test_non_advisor_role_cannot_access_advisor_resources(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse("dashboard:advisor")).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("dashboard:advisor")).status_code, 404)

    def test_advisor_cannot_browse_unrelated_advisee_or_publication_by_url(self):
        self.client.force_login(self.advisor_a_user)
        self.assertEqual(
            self.client.get(reverse("dashboard:advisor_advisee_publications", args=[self.other_student.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:advisor_publication_detail", args=[self.other_publication.id])).status_code,
            404,
        )

    def test_inactive_advising_relationship_does_not_grant_access(self):
        StudentAdvisor.objects.create(student=self.other_student, professor=self.advisor_a, is_active=False)
        self.client.force_login(self.advisor_a_user)
        self.assertEqual(
            self.client.get(reverse("dashboard:advisor_advisee_publications", args=[self.other_student.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:advisor_publication_detail", args=[self.other_publication.id])).status_code,
            404,
        )

    def test_visibility_scopes_allow_owner_advisor_and_department_but_not_staff_only(self):
        staff_only = self.publication()
        staff_only.title = "Staff only record"
        staff_only.visibility_scope = PublicationRecord.VisibilityScope.STAFF_ONLY
        staff_only.save()
        department = self.publication()
        department.title = "Department record"
        department.workflow_status = PublicationRecord.WorkflowStatus.APPROVED
        department.is_published = True
        department.visibility_scope = PublicationRecord.VisibilityScope.DEPARTMENT_ALL
        department.save()
        department.series.current_official_version = department
        department.series.save(update_fields=["current_official_version", "updated_at"])
        # The advisor screen intentionally keeps advisor visibility even for a
        # multi-role account; staff-only access belongs to the staff workflow.
        UserRole.objects.create(user=self.advisor_a_user, role=self.staff_role)
        self.client.force_login(self.advisor_a_user)
        listing = self.client.get(reverse("dashboard:advisor_advisee_publications", args=[self.student.id]))
        self.assertContains(listing, self.own_publication.title)
        self.assertContains(listing, department.title)
        self.assertNotContains(listing, staff_only.title)
        self.assertEqual(
            self.client.get(reverse("dashboard:advisor_publication_detail", args=[self.own_publication.id])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:advisor_publication_detail", args=[staff_only.id])).status_code,
            404,
        )

    def test_advisor_cannot_approve_or_return(self):
        self.complete(self.own_publication)
        submit_publication(actor=self.student_user, publication_id=self.own_publication.id)
        self.client.force_login(self.advisor_a_user)
        self.assertEqual(self.client.post(reverse("review:approve", args=[self.own_publication.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("review:return_publication", args=[self.own_publication.id])).status_code, 404)
        self.own_publication.refresh_from_db()
        self.assertEqual(self.own_publication.workflow_status, PublicationRecord.WorkflowStatus.SUBMITTED)

    def test_authorized_private_download_works_and_unrelated_advisor_cannot_find_it(self):
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                document = upload_document(
                    actor=self.student_user,
                    publication=self.own_publication,
                    upload=SimpleUploadedFile("advisor-evidence.pdf", b"%PDF-1.4 evidence", content_type="application/pdf"),
                )
                self.client.force_login(self.advisor_a_user)
                detail = self.client.get(reverse("dashboard:advisor_publication_detail", args=[self.own_publication.id]))
                self.assertContains(detail, document.original_filename)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 200)
                self.client.force_login(self.advisor_b_user)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)

    def test_document_download_cannot_bypass_staff_only_parent_visibility(self):
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                self.own_publication.visibility_scope = PublicationRecord.VisibilityScope.STAFF_ONLY
                self.own_publication.save(update_fields=["visibility_scope"])
                document = upload_document(
                    actor=self.student_user,
                    publication=self.own_publication,
                    upload=SimpleUploadedFile("staff-only.pdf", b"%PDF-1.4 evidence", content_type="application/pdf"),
                )
                self.client.force_login(self.advisor_a_user)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)
                self.client.force_login(self.student_user)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 200)
                self.client.force_login(self.staff)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 200)

    def test_archived_advisor_cannot_download_document_through_active_relation(self):
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                document = upload_document(
                    actor=self.student_user,
                    publication=self.own_publication,
                    upload=SimpleUploadedFile("archived-advisor.pdf", b"%PDF-1.4 evidence", content_type="application/pdf"),
                )
                self.advisor_a.status = Professor.Status.ARCHIVED
                self.advisor_a.save(update_fields=["status"])
                self.client.force_login(self.advisor_a_user)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)

    def test_inactive_replaced_document_uuid_is_not_downloadable(self):
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                original = upload_document(
                    actor=self.student_user,
                    publication=self.own_publication,
                    upload=SimpleUploadedFile("original.pdf", b"%PDF-1.4 original", content_type="application/pdf"),
                )
                replacement = upload_document(
                    actor=self.student_user,
                    publication=self.own_publication,
                    upload=SimpleUploadedFile("replacement.pdf", b"%PDF-1.4 replacement", content_type="application/pdf"),
                    supersedes=original,
                )
                original.refresh_from_db()
                self.assertFalse(original.is_active)
                for user in (self.student_user, self.staff, self.advisor_a_user):
                    self.client.force_login(user)
                    self.assertEqual(self.client.get(reverse("documents:download", args=[original.id])).status_code, 404)
                self.client.force_login(self.advisor_a_user)
                self.assertEqual(self.client.get(reverse("documents:download", args=[replacement.id])).status_code, 200)
