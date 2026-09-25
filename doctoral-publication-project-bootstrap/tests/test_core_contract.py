from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from pathlib import Path
from tempfile import TemporaryDirectory

from accounts.models import Role, User, UserRole
from advising.models import StudentAdvisor
from documents.services import open_document_for_download, upload_document
from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from publications.models import PublicationAuthor, PublicationRecord
from publications.permissions import can_view_publication
from publications.services import create_publication, set_published, set_visibility, submit_publication
from review.services import approve_publication, return_for_revision
from reporting.services import approved_publications, student_summary
from taxonomy.models import PublicationType
from documents.models import SourceDocument


class ContractFixture(TestCase):
    def setUp(self):
        self.student_role = Role.objects.create(slug="student", display_name="Student")
        self.advisor_role = Role.objects.create(slug="advisor", display_name="Advisor")
        self.staff_role = Role.objects.create(slug="staff", display_name="Staff")
        self.type = PublicationType.objects.create(slug="journal", display_name="Journal")
        self.student_user = self.user("student", self.student_role)
        self.other_student_user = self.user("other", self.student_role)
        self.staff = self.user("staff", self.staff_role)
        self.student = DoctoralStudentProfile.objects.create(user=self.student_user, student_number="D001", display_name="Student A", admission_year=111)
        self.other_student = DoctoralStudentProfile.objects.create(user=self.other_student_user, student_number="D002", display_name="Student B", admission_year=111)

    def user(self, username, role):
        user = User.objects.create_user(username=username, email=f"{username}@example.edu", password="pass")
        UserRole.objects.create(user=user, role=role)
        return user

    def publication(self):
        return create_publication(actor=self.student_user, owner_student=self.student, publication_type=self.type, title="A governed publication")

    def complete(self, publication):
        PublicationAuthor.objects.get_or_create(publication=publication, author_order=1, defaults={"display_name": "Student A"})
        SourceDocument.objects.get_or_create(publication=publication, checksum_sha256="a" * 64, defaults={
            "document_type": SourceDocument.DocumentType.OTHER, "original_filename": "evidence.pdf", "storage_key": f"test/{publication.id}",
            "mime_type": "application/pdf", "file_size": 16, "uploaded_by": self.student_user,
        })


class WorkflowAndStatisticsTests(ContractFixture):
    def test_only_staff_can_approve_and_only_approved_counts(self):
        publication = self.publication()
        self.assertEqual(approved_publications().count(), 0)
        with self.assertRaises(PermissionDenied):
            approve_publication(actor=self.student_user, publication_id=publication.id)
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        approve_publication(actor=self.staff, publication_id=publication.id)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.APPROVED)
        self.assertEqual(approved_publications().count(), 1)
        self.assertEqual(student_summary(self.student)["approved_total"], 1)
        self.assertEqual(publication.transitions.count(), 3)
        self.assertEqual(publication.review_decisions.count(), 1)

    def test_return_allows_resubmission_but_illegal_transition_fails(self):
        publication = self.publication()
        with self.assertRaises(ValidationError):
            return_for_revision(actor=self.staff, publication_id=publication.id)
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        return_for_revision(actor=self.staff, publication_id=publication.id, reason="Need evidence")
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.RETURNED)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        self.assertEqual(publication.transitions.count(), 4)

    def test_author_order_is_unique(self):
        publication = self.publication()
        PublicationAuthor.objects.create(publication=publication, display_name="Student A", author_order=1)
        with self.assertRaises(Exception):
            PublicationAuthor.objects.create(publication=publication, display_name="Coauthor", author_order=1)


class VisibilityAndDocumentTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.advisor_user = self.user("advisor", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="Advisor A")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor)

    def approved_owner_advisor_publication(self):
        publication = self.publication()
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        return approve_publication(actor=self.staff, publication_id=publication.id)

    def test_owner_advisor_isolation_and_staff_gate(self):
        publication = self.approved_owner_advisor_publication()
        self.assertTrue(can_view_publication(self.student_user, publication))
        self.assertTrue(can_view_publication(self.advisor_user, publication))
        self.assertTrue(can_view_publication(self.staff, publication))
        self.assertFalse(can_view_publication(self.other_student_user, publication))
        set_visibility(actor=self.staff, publication_id=publication.id, visibility_scope=PublicationRecord.VisibilityScope.PUBLIC)
        set_published(actor=self.staff, publication_id=publication.id, is_published=True)
        publication.refresh_from_db()
        self.assertTrue(can_view_publication(None, publication))

    def test_private_document_download_requires_parent_permission(self):
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                publication = self.publication()
                upload = SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 evidence", content_type="application/pdf")
                document = upload_document(actor=self.student_user, publication=publication, upload=upload)
                with self.assertRaises(PermissionDenied):
                    open_document_for_download(actor=self.other_student_user, document=document)
                with open_document_for_download(actor=self.student_user, document=document) as stream:
                    self.assertEqual(stream.read(), b"%PDF-1.4 evidence")
