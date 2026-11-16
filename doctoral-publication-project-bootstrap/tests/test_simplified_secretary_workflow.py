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
from review.services import approve_publication, return_for_revision
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

    def test_secretary_filtered_type_lists_export_csv_and_xlsx_with_review_status(self):
        submitted = self._submitted("匯出待審")
        approved = self._submitted("匯出核可")
        returned = self._submitted("匯出駁回")
        trashed = self._submitted("匯出垃圾桶")
        approve_publication(actor=self.staff, publication_id=approved.id)
        return_for_revision(actor=self.staff, publication_id=returned.id, reason="請補正")
        trash_publication(actor=self.staff, publication_id=trashed.id)
        self.client.force_login(self.staff)

        all_records = self.client.get(reverse("review:journal_list"), {"status": "all"})
        self.assertContains(all_records, submitted.title)
        self.assertContains(all_records, approved.title)
        self.assertContains(all_records, returned.title)
        self.assertNotContains(all_records, trashed.title)

        csv_response = self.client.get(reverse("review:export", args=["journal"]), {"status": "all", "format": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")
        csv_content = csv_response.content.decode("utf-8-sig")
        self.assertIn("審核狀態", csv_content)
        self.assertIn("已送審", csv_content)
        self.assertIn("已核准", csv_content)
        self.assertIn("已退回", csv_content)
        self.assertNotIn(trashed.title, csv_content)

        xlsx_response = self.client.get(reverse("review:export", args=["journal"]), {"status": "all", "format": "xlsx"})
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertTrue(xlsx_response.content.startswith(b"PK"))
