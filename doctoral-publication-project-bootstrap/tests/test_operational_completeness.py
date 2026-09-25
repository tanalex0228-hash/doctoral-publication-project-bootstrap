from datetime import date
from unittest.mock import patch

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User, UserRole
from advising.models import StudentAdvisor
from audit.models import AuditLog
from config.pagination import DEFAULT_PAGE_SIZE
from documents.models import SourceDocument
from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from publications.models import PublicationAuthor, PublicationRecord
from publications.services import create_publication, set_published, set_visibility, submit_publication
from reporting.services import approved_publications
from review.services import approve_publication
from taxonomy.models import PublicationIndex, PublicationType, ResearchField
from tests.test_core_contract import ContractFixture


class ArchiveAndCsvTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.admin_role = Role.objects.create(slug="admin", display_name="Admin")
        self.admin = self.user("archive-admin", self.admin_role)
        self.advisor_user = self.user("archive-advisor", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="Archive Advisor")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor)
        self.is_staff_only = User.objects.create_user(
            username="archive-django-staff",
            email="archive-django-staff@example.edu",
            password="pass",
            is_staff=True,
        )

    def approved_publication(self, title="Archive target", publication_date=date(2024, 6, 1)):
        publication = create_publication(
            actor=self.student_user,
            owner_student=self.student,
            publication_type=self.type,
            title=title,
            publication_date=publication_date,
        )
        PublicationAuthor.objects.create(publication=publication, display_name=self.student.display_name, author_order=1)
        SourceDocument.objects.create(
            publication=publication,
            document_type="other",
            original_filename="private.pdf",
            storage_key=f"operational/{publication.id}",
            mime_type="application/pdf",
            file_size=8,
            checksum_sha256=f"{publication.id.int:064x}",
            uploaded_by=self.student_user,
        )
        submit_publication(actor=self.student_user, publication_id=publication.id)
        approve_publication(actor=self.staff, publication_id=publication.id)
        set_visibility(actor=self.staff, publication_id=publication.id, visibility_scope=PublicationRecord.VisibilityScope.PUBLIC)
        set_published(actor=self.staff, publication_id=publication.id, is_published=True)
        return publication

    def test_archive_requires_project_role_and_creates_workflow_audit_evidence(self):
        publication = self.approved_publication()
        for user in (self.student_user, self.advisor_user, self.is_staff_only):
            self.client.force_login(user)
            self.assertEqual(self.client.post(reverse("review:archive", args=[publication.id])).status_code, 404)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("review:archive", args=[publication.id]))
        self.assertEqual(response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.workflow_status, PublicationRecord.WorkflowStatus.ARCHIVED)
        self.assertTrue(publication.transitions.filter(to_status="archived", actor=self.staff).exists())
        self.assertTrue(publication.review_decisions.filter(action="archive", reviewer=self.staff).exists())
        self.assertTrue(AuditLog.objects.filter(action="publication.archived", target_id=publication.id).exists())

    def test_archived_record_leaves_active_surfaces_but_remains_in_archive_history(self):
        publication = self.approved_publication()
        self.client.force_login(self.admin)
        self.client.post(reverse("review:archive", args=[publication.id]))
        self.assertNotIn(publication.id, approved_publications().values_list("id", flat=True))
        self.assertNotContains(self.client.get(reverse("review:queue")), publication.title)
        self.assertContains(self.client.get(reverse("review:archive_list")), publication.title)
        self.assertEqual(self.client.get(reverse("public_site:publication_detail", args=[publication.id])).status_code, 404)

    def test_archive_does_not_widen_private_document_permission(self):
        publication = self.approved_publication()
        document = publication.documents.get()
        self.client.force_login(self.staff)
        self.client.post(reverse("review:archive", args=[publication.id]))
        self.client.force_login(self.other_student_user)
        self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)

    def test_csv_is_staff_gated_approved_only_filtered_utf8_and_formula_safe(self):
        self.student.display_name = "王小明"
        self.student.save(update_fields=["display_name"])
        approved = self.approved_publication(title="=公式注入", publication_date=date(2024, 6, 1))
        draft = create_publication(
            actor=self.student_user,
            owner_student=self.student,
            publication_type=self.type,
            title="Draft not exported",
            publication_date=date(2024, 6, 2),
        )
        for user in (self.student_user, self.advisor_user, self.is_staff_only):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("statistics:csv_export")).status_code, 404)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("statistics:csv_export"), {"year": 2024})
        content = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("王小明", content)
        self.assertIn("'=公式注入", content)
        self.assertNotIn(draft.title, content)
        self.assertIn(approved.title[1:], content)

    def test_csv_view_reuses_existing_export_service(self):
        self.client.force_login(self.staff)
        with patch("reporting.views.export_ready_rows", return_value=[]) as export_rows:
            response = self.client.get(reverse("statistics:csv_export"))
        self.assertEqual(response.status_code, 200)
        export_rows.assert_called_once()

    def test_taxonomy_admin_supports_active_state_and_display_order(self):
        from taxonomy.admin import TaxonomyAdmin

        self.assertIsInstance(admin.site._registry[PublicationType], TaxonomyAdmin)
        self.assertEqual(admin.site._registry[PublicationIndex].list_editable, ("is_active", "display_order"))
        self.assertEqual(admin.site._registry[ResearchField].list_display, ("display_name", "slug", "is_active", "display_order"))


class PaginationTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.advisor_user = self.user("pagination-advisor", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="Pagination Advisor")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor)
        self._make_public_records(DEFAULT_PAGE_SIZE + 1)

    def _make_public_records(self, count):
        for number in range(count):
            PublicationRecord.objects.create(
                owner_student=self.student,
                publication_type=self.type,
                title=f"Paginated Public {number:02d}",
                workflow_status=PublicationRecord.WorkflowStatus.APPROVED,
                is_published=True,
                visibility_scope=PublicationRecord.VisibilityScope.PUBLIC,
                publication_date=date(2025, 1, 1),
                created_by=self.student_user,
                updated_by=self.student_user,
            )

    def test_public_department_advisor_and_export_lists_paginate_safely_and_keep_query(self):
        public_page_one = self.client.get(reverse("public_site:publication_list"), {"q": "Paginated Public", "page": 1})
        public_page_two = self.client.get(reverse("public_site:publication_list"), {"q": "Paginated Public", "page": 2})
        self.assertContains(public_page_one, "Paginated Public 00")
        self.assertNotContains(public_page_one, "Paginated Public 25")
        self.assertContains(public_page_two, "Paginated Public 25")
        self.assertContains(public_page_one, "q=Paginated+Public")
        self.assertEqual(self.client.get(reverse("public_site:publication_list"), {"page": "not-a-number"}).context["page_obj"].number, 1)
        self.client.force_login(self.student_user)
        self.assertContains(self.client.get(reverse("public_site:department_list"), {"page": 2}), "Paginated Public 25")
        self.client.force_login(self.advisor_user)
        advisor_page_two = self.client.get(
            reverse("dashboard:advisor_advisee_publications", args=[self.student.id]), {"page": 2}
        )
        self.assertEqual(advisor_page_two.context["page_obj"].number, 2)
        self.assertEqual(advisor_page_two.context["page_obj"].paginator.count, DEFAULT_PAGE_SIZE + 1)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("statistics:export_ready"), {"page": 2}), "Paginated Public 25")

    def test_review_queue_pagination_preserves_sort_and_has_safe_last_page(self):
        for number in range(DEFAULT_PAGE_SIZE + 1):
            PublicationRecord.objects.create(
                owner_student=self.student,
                publication_type=self.type,
                title=f"Paginated submitted {number:02d}",
                workflow_status=PublicationRecord.WorkflowStatus.SUBMITTED,
                submitted_at=timezone.now(),
                created_by=self.student_user,
                updated_by=self.student_user,
            )
        self.client.force_login(self.staff)
        first = self.client.get(reverse("review:queue"), {"sort": "title", "page": 1})
        second = self.client.get(reverse("review:queue"), {"sort": "title", "page": 2})
        self.assertContains(first, "Paginated submitted 00")
        self.assertContains(second, "Paginated submitted 25")
        self.assertContains(first, "sort=title")
        self.assertEqual(self.client.get(reverse("review:queue"), {"page": 999}).context["page_obj"].number, 2)
