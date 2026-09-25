from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from accounts.models import Role, User
from advising.models import StudentAdvisor
from documents.models import SourceDocument
from documents.services import upload_document
from professors.models import Professor
from publications.models import PublicationAuthor, PublicationRecord
from publications.services import create_publication, submit_publication
from reporting.services import approved_publications
from review.services import approve_publication, return_for_revision
from taxonomy.models import PublicationIndex, PublicationType, ResearchField
from tests.test_core_contract import ContractFixture


class StatisticsVerticalSliceTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.admin_role = Role.objects.create(slug="admin", display_name="Admin")
        self.admin = self.user("admin-statistics", self.admin_role)
        self.is_staff_only = User.objects.create_user(
            username="django-staff-only-statistics",
            email="django-staff-only-statistics@example.edu",
            password="pass",
            is_staff=True,
        )
        self.advisor_user = self.user("advisor-statistics", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="Advisor A")
        self.other_advisor = Professor.objects.create(display_name="Advisor B")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor)
        StudentAdvisor.objects.create(student=self.other_student, professor=self.other_advisor)
        self.conference_type = PublicationType.objects.create(slug="conference", display_name="Conference")
        self.index_a = PublicationIndex.objects.create(slug="sci", display_name="SCI")
        self.index_b = PublicationIndex.objects.create(slug="ssci", display_name="SSCI")
        self.field_a = ResearchField.objects.create(slug="finance", display_name="Finance")
        self.field_b = ResearchField.objects.create(slug="marketing", display_name="Marketing")
        self.approved_a = self._record(
            owner=self.student,
            actor=self.student_user,
            publication_type=self.type,
            title="Approved journal 2024",
            publication_date=date(2024, 5, 20),
            accepted_date=date(2024, 3, 15),
            publication_index=self.index_a,
            research_field=self.field_a,
            language="en",
            state="approved",
        )
        self.approved_b = self._record(
            owner=self.other_student,
            actor=self.other_student_user,
            publication_type=self.conference_type,
            title="Approved conference 2025",
            publication_date=date(2025, 6, 1),
            accepted_date=date(2025, 4, 1),
            publication_index=self.index_b,
            research_field=self.field_b,
            language="zh-Hant",
            state="approved",
        )
        self.draft = self._record(
            owner=self.student,
            actor=self.student_user,
            publication_type=self.type,
            title="Draft excluded",
            publication_date=date(2024, 1, 1),
            publication_index=self.index_a,
            research_field=self.field_a,
            state="draft",
        )
        self.submitted = self._record(
            owner=self.student,
            actor=self.student_user,
            publication_type=self.type,
            title="Submitted excluded",
            publication_date=date(2024, 1, 2),
            publication_index=self.index_a,
            research_field=self.field_a,
            state="submitted",
        )
        self.returned = self._record(
            owner=self.student,
            actor=self.student_user,
            publication_type=self.type,
            title="Returned excluded",
            publication_date=date(2024, 1, 3),
            publication_index=self.index_a,
            research_field=self.field_a,
            state="returned",
        )

    def _record(self, *, owner, actor, publication_type, title, publication_date,
                publication_index, research_field, state, accepted_date=None, language="en"):
        publication = create_publication(
            actor=actor,
            owner_student=owner,
            publication_type=publication_type,
            title=title,
            publication_date=publication_date,
            accepted_date=accepted_date,
            language=language,
        )
        publication.indices.add(publication_index)
        publication.research_fields.add(research_field)
        PublicationAuthor.objects.create(
            publication=publication,
            display_name=owner.display_name,
            author_order=1,
            linked_user=owner.user,
            is_corresponding_author=True,
        )
        SourceDocument.objects.create(
            publication=publication,
            document_type=SourceDocument.DocumentType.OTHER,
            original_filename=f"{title}.pdf",
            storage_key=f"statistics/{publication.id}",
            mime_type="application/pdf",
            file_size=8,
            checksum_sha256=f"{publication.id.int:064x}",
            uploaded_by=actor,
        )
        if state == "draft":
            return publication
        submit_publication(actor=actor, publication_id=publication.id)
        if state == "submitted":
            return publication
        if state == "returned":
            return return_for_revision(actor=self.staff, publication_id=publication.id)
        return approve_publication(actor=self.staff, publication_id=publication.id)

    def _export(self, **params):
        self.client.force_login(self.staff)
        return self.client.get(reverse("statistics:export_ready"), params)

    def test_statistics_dashboard_allows_only_project_staff_or_admin(self):
        for user in (self.student_user, self.advisor_user, self.is_staff_only):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("statistics:dashboard")).status_code, 404)
        for user in (self.staff, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("statistics:dashboard")).status_code, 200)

    def test_draft_submitted_and_returned_never_enter_official_statistics(self):
        self.assertEqual(approved_publications().count(), 2)
        self.client.force_login(self.staff)
        dashboard = self.client.get(reverse("statistics:dashboard"))
        self.assertEqual(dashboard.context["overview"]["approved_total"], 2)
        detail = self.client.get(reverse("statistics:student_detail", args=[self.student.id]))
        self.assertContains(detail, self.approved_a.title)
        self.assertNotContains(detail, self.draft.title)
        self.assertNotContains(detail, self.submitted.title)
        self.assertNotContains(detail, self.returned.title)
        student_list = self.client.get(reverse("statistics:students"))
        rows = {row.student_number: row for row in student_list.context["students"]}
        self.assertEqual(rows[self.student.student_number].approved_total, 1)
        self.assertEqual(rows[self.student.student_number].journal_total, 1)
        self.assertEqual(rows[self.student.student_number].conference_total, 0)
        self.assertEqual(rows[self.other_student.student_number].conference_total, 1)

    def test_approval_updates_statistics_immediately(self):
        pending = self._record(
            owner=self.student,
            actor=self.student_user,
            publication_type=self.type,
            title="Approved after dashboard load",
            publication_date=date(2026, 1, 1),
            publication_index=self.index_a,
            research_field=self.field_a,
            state="submitted",
        )
        self.client.force_login(self.staff)
        before = self.client.get(reverse("statistics:dashboard"))
        self.assertEqual(before.context["overview"]["approved_total"], 2)
        approve_publication(actor=self.staff, publication_id=pending.id)
        after = self.client.get(reverse("statistics:dashboard"))
        self.assertEqual(after.context["overview"]["approved_total"], 3)

    def test_filters_apply_only_to_approved_records(self):
        cases = [
            ({"student": self.student.id}, self.approved_a.title, self.approved_b.title),
            ({"year": 2024}, self.approved_a.title, self.approved_b.title),
            ({"publication_type": self.conference_type.id}, self.approved_b.title, self.approved_a.title),
            ({"publication_index": self.index_a.id}, self.approved_a.title, self.approved_b.title),
            ({"advisor": self.advisor.id}, self.approved_a.title, self.approved_b.title),
            ({"research_field": self.field_b.id, "language": "zh-Hant"}, self.approved_b.title, self.approved_a.title),
            ({"author_role": "first_author", "date_from": "2024-01-01", "date_to": "2024-12-31"}, self.approved_a.title, self.approved_b.title),
        ]
        for params, included, excluded in cases:
            response = self._export(**params)
            self.assertContains(response, included)
            self.assertNotContains(response, excluded)
            self.assertNotContains(response, self.draft.title)

    def test_student_statistics_sorting_uses_allowlist(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("statistics:students"), {"sort": "approved_count"})
        self.assertEqual(response.context["sort"], "approved_count")
        response = self.client.get(reverse("statistics:students"), {"sort": "owner_student__user__password"})
        self.assertEqual(response.context["sort"], "name")

    def test_statistics_drill_down_uses_existing_staff_detail_and_private_download(self):
        with TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory)):
                publication = create_publication(
                    actor=self.student_user,
                    owner_student=self.student,
                    publication_type=self.type,
                    title="Approved evidence drill-down",
                )
                document = upload_document(
                    actor=self.student_user,
                    publication=publication,
                    upload=SimpleUploadedFile("statistics-evidence.pdf", b"%PDF-1.4 evidence", content_type="application/pdf"),
                )
                PublicationAuthor.objects.create(publication=publication, display_name=self.student.display_name, author_order=1)
                submit_publication(actor=self.student_user, publication_id=publication.id)
                approve_publication(actor=self.staff, publication_id=publication.id)
                self.client.force_login(self.staff)
                export = self.client.get(reverse("statistics:export_ready"))
                self.assertContains(export, reverse("review:detail", args=[publication.id]))
                detail = self.client.get(reverse("review:detail", args=[publication.id]))
                self.assertContains(detail, document.original_filename)
                self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 200)
