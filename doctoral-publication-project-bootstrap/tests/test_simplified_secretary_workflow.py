from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from publications.models import PublicationAuthor, PublicationRecord
from publications.services import (
    restore_trashed_publication,
    purge_trashed_publication,
    submit_publication,
    trash_publication,
    update_publication,
)
from review.services import return_for_revision
from tests.test_core_contract import ContractFixture


class SimplifiedSecretaryWorkflowTests(ContractFixture):
    def _submitted(self, title="待審成果"):
        publication = self.publication()
        publication.title = title
        publication.save(update_fields=["title", "normalized_title"])
        self.complete(publication)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        return publication

    def test_owner_can_edit_submitted_until_secretary_decides(self):
        publication = self._submitted()
        update_publication(
            actor=self.student_user, publication_id=publication.id,
            publication_type=publication.publication_type, title="待審期間修正",
            journal_or_conference_name="", doi=None, issn=None,
            publication_stage=PublicationRecord.PublicationStage.PUBLISHED,
            publication_date=None,
        )
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.SUBMITTED)
        self.assertEqual(publication.title, "待審期間修正")

    def test_submission_count_starts_at_one_and_increments_after_return(self):
        publication = self._submitted()
        self.assertEqual(publication.submission_count, 1)
        return_for_revision(actor=self.staff, publication_id=publication.id, reason="請補正")
        submit_publication(actor=self.student_user, publication_id=publication.id)
        publication.refresh_from_db()
        self.assertEqual(publication.submission_count, 2)

    def test_student_author_metadata_belongs_to_each_system_student_author(self):
        publication = self.publication()
        author = PublicationAuthor.objects.create(
            publication=publication, display_name=self.student.display_name, author_order=1,
            linked_user=self.student_user, is_system_student=True,
            student_author_order=PublicationAuthor.StudentAuthorOrder.FIRST,
            student_author_attribute=PublicationAuthor.StudentAuthorAttribute.FIRST_AUTHOR,
            is_student_corresponding_author=True,
        )
        self.assertTrue(author.is_system_student)
        self.assertEqual(author.student_author_order, "first")
        self.assertTrue(author.is_student_corresponding_author)

    def test_trash_hides_record_until_staff_restores_it(self):
        publication = self.publication()
        trash_publication(actor=self.student_user, publication_id=publication.id)
        publication.refresh_from_db()
        self.assertTrue(publication.is_trashed)
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse("publications:detail", args=[publication.id])).status_code, 404)
        restore_trashed_publication(actor=self.staff, publication_id=publication.id)
        publication.refresh_from_db()
        self.assertFalse(publication.is_trashed)

    def test_only_root_can_permanently_clear_a_trashed_record_and_keep_audit(self):
        publication = self.publication()
        self.complete(publication)
        trash_publication(actor=self.student_user, publication_id=publication.id)
        with self.assertRaises(Exception):
            purge_trashed_publication(actor=self.staff, publication_id=publication.id)
        root = User.objects.create_superuser("root-clear", "root-clear@example.edu", "pass")
        purge_trashed_publication(actor=root, publication_id=publication.id)
        publication.refresh_from_db()
        self.assertTrue(publication.is_purged)
        self.assertEqual(publication.title, "已清除的成果")
        self.assertFalse(publication.documents.filter(is_active=True).exists())
        self.assertTrue(AuditLog.objects.filter(action="publication.purged", target_id=publication.id).exists())

    def test_secretary_type_list_filters_status_and_keeps_trash_separate(self):
        submitted = self._submitted("期刊待審")
        trashed = self._submitted("期刊垃圾桶")
        trash_publication(actor=self.staff, publication_id=trashed.id)
        self.client.force_login(self.staff)
        pending = self.client.get(reverse("review:journal_list"))
        self.assertContains(pending, submitted.title)
        self.assertNotContains(pending, trashed.title)
        trash = self.client.get(reverse("review:journal_list"), {"status": "trash"})
        self.assertContains(trash, trashed.title)
        self.assertNotContains(trash, submitted.title)
