from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from accounts.models import UserRole
from advising.models import StudentAdvisor
from documents.models import SourceDocument
from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from publications.forms import PublicationForm
from publications.models import PublicationAuthor, PublicationRecord
from publications.permissions import can_view_publication
from publications.services import create_revision, set_published, set_visibility, submit_publication
from publications.querysets import official_publications
from reporting.portable_export import document_manifest, rows_for
from reporting.services import approved_publications, student_summary
from review.models import ReviewDecision
from review.services import approve_publication, archive_publication, return_for_revision, revoke_approval
from tests.test_core_contract import ContractFixture


class Rc2DomainReconciliationTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.advisor_user = self.user("rc2-advisor", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="RC2 Advisor")
        self.relation = StudentAdvisor.objects.create(
            student=self.student,
            professor=self.advisor,
            end_date=date.today() - timedelta(days=1),
        )

    def approved(self, title="RC2 official"):
        publication = self.publication()
        publication.title = title
        publication.save()
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        return approve_publication(actor=self.staff, publication_id=publication.id)

    def test_valid_official_contract_includes_archived_but_excludes_revoked(self):
        publication = self.approved()
        self.assertTrue(official_publications().filter(pk=publication.id).exists())
        archive_publication(actor=self.staff, publication_id=publication.id)
        self.assertTrue(approved_publications().filter(pk=publication.id).exists())
        revoke_approval(actor=self.staff, publication_id=publication.id, reason="Governance correction")
        self.assertFalse(official_publications().filter(pk=publication.id).exists())
        self.assertEqual(student_summary(self.student)["approved_total"], 0)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.REVOKED)
        self.assertTrue(publication.review_decisions.filter(action=ReviewDecision.Action.REVOKE).exists())
        self.assertTrue(publication.transitions.filter(to_status=PublicationRecord.WorkflowStatus.REVOKED).exists())

    def test_revision_keeps_old_official_until_new_revision_is_approved(self):
        original = self.approved("Original official")
        set_visibility(actor=self.staff, publication_id=original.id, visibility_scope=PublicationRecord.VisibilityScope.PUBLIC)
        set_published(actor=self.staff, publication_id=original.id, is_published=True)
        original.refresh_from_db()
        revision = create_revision(actor=self.student_user, publication_id=original.id)
        revision.title = "Pending correction"
        revision.save(update_fields=["title", "normalized_title", "updated_at"])
        submit_publication(actor=self.student_user, publication_id=revision.id)
        original.series.refresh_from_db()
        self.assertEqual(original.series.current_official_version_id, original.id)
        self.assertTrue(can_view_publication(None, original))
        self.assertFalse(can_view_publication(None, revision))
        return_for_revision(actor=self.staff, publication_id=revision.id, reason="Clarify title")
        original.series.refresh_from_db()
        self.assertEqual(original.series.current_official_version_id, original.id)
        submit_publication(actor=self.student_user, publication_id=revision.id)
        approve_publication(actor=self.staff, publication_id=revision.id)
        revision.refresh_from_db()
        original.series.refresh_from_db()
        self.assertEqual(original.series.current_official_version_id, revision.id)
        self.assertFalse(can_view_publication(None, original))
        self.assertTrue(can_view_publication(None, revision))

    def test_end_date_does_not_remove_advisor_access_but_inactive_or_archived_does(self):
        publication = self.approved()
        self.assertTrue(can_view_publication(self.advisor_user, publication))
        self.relation.is_active = False
        self.relation.save(update_fields=["is_active"])
        self.assertFalse(can_view_publication(self.advisor_user, publication))
        self.relation.is_active = True
        self.relation.save(update_fields=["is_active"])
        self.advisor.status = Professor.Status.ARCHIVED
        self.advisor.save(update_fields=["status"])
        self.assertFalse(can_view_publication(self.advisor_user, publication))

    def test_visibility_scope_contract_is_explicit(self):
        publication = self.approved()
        other_faculty_user = self.user("rc2-faculty", self.advisor_role)
        Professor.objects.create(user=other_faculty_user, display_name="Other Faculty")
        set_visibility(actor=self.staff, publication_id=publication.id, visibility_scope=PublicationRecord.VisibilityScope.OWNER_FACULTY)
        publication.refresh_from_db()
        self.assertTrue(can_view_publication(other_faculty_user, publication))
        self.assertFalse(can_view_publication(self.other_student_user, publication))
        set_visibility(actor=self.staff, publication_id=publication.id, visibility_scope=PublicationRecord.VisibilityScope.STAFF_ONLY)
        publication.refresh_from_db()
        self.assertFalse(can_view_publication(self.advisor_user, publication))
        self.assertFalse(can_view_publication(self.other_student_user, publication))
        self.assertTrue(can_view_publication(self.staff, publication))

    def test_revoke_is_staff_only_and_preserves_audit_evidence(self):
        publication = self.approved()
        with self.assertRaises(PermissionDenied):
            revoke_approval(actor=self.student_user, publication_id=publication.id, reason="No authority")
        revoke_approval(actor=self.staff, publication_id=publication.id, reason="Validated correction")
        self.assertEqual(publication.review_decisions.filter(action="revoke").count(), 1)

    def test_issn_check_digit_and_portable_metadata_contract(self):
        form_data = {"publication_type": self.type.id, "title": "ISSN test", "issn": "0317-8471", "language": "zh-Hant", "publication_stage": "published"}
        valid = PublicationForm(data=form_data)
        self.assertTrue(valid.is_valid(), valid.errors)
        invalid = PublicationForm(data={**form_data, "issn": "0317-8472"})
        self.assertFalse(invalid.is_valid())
        publication = self.approved()
        document = publication.documents.get()
        self.assertEqual(document_manifest()[0]["checksum_sha256"], document.checksum_sha256)
        publication_rows = list(rows_for(PublicationRecord))
        self.assertEqual(publication_rows[0]["id"], str(publication.id))
