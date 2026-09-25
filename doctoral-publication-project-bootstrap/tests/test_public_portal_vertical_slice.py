from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User, UserRole
from documents.models import SourceDocument
from doctoral_students.models import DoctoralStudentProfile
from publications.models import PublicationAuthor, PublicationRecord
from publications.services import create_publication, set_published, set_visibility, submit_publication
from review.services import approve_publication
from taxonomy.models import PublicationIndex, PublicationType, ResearchField


class PublicPortalVerticalSliceTests(TestCase):
    def setUp(self):
        self.student_role = Role.objects.create(slug="student", display_name="Student")
        self.staff_role = Role.objects.create(slug="staff", display_name="Staff")
        self.publication_type = PublicationType.objects.create(slug="journal", display_name="Journal")
        self.other_type = PublicationType.objects.create(slug="conference", display_name="Conference")
        self.index = PublicationIndex.objects.create(slug="ssci", display_name="SSCI")
        self.field = ResearchField.objects.create(slug="management", display_name="Management")
        self.student_user = self._user("portal-owner", self.student_role)
        self.department_user = self._user("portal-department", self.student_role)
        self.staff = self._user("portal-staff", self.staff_role)
        self.is_staff_only = User.objects.create_user(
            username="portal-django-staff-only",
            email="portal-django-staff-only@example.edu",
            password="pass",
            is_staff=True,
        )
        self.student = DoctoralStudentProfile.objects.create(
            user=self.student_user,
            student_number="P001",
            display_name="Portal Owner",
            admission_year=112,
        )
        self.public_record = self._approved_record(
            title="Public research result",
            visibility=PublicationRecord.VisibilityScope.PUBLIC,
            published=True,
        )
        self.unpublished = self._approved_record(
            title="Approved but unpublished",
            visibility=PublicationRecord.VisibilityScope.PUBLIC,
            published=False,
        )
        self.department_record = self._approved_record(
            title="Department only result",
            visibility=PublicationRecord.VisibilityScope.DEPARTMENT,
            published=True,
        )
        self.owner_advisor = self._approved_record(
            title="Owner advisor result",
            visibility=PublicationRecord.VisibilityScope.OWNER_ADVISOR,
            published=True,
        )
        self.staff_only = self._approved_record(
            title="Staff only result",
            visibility=PublicationRecord.VisibilityScope.STAFF_ONLY,
            published=True,
        )
        self.submitted = self._submitted_public_looking_record()

    def _user(self, username, role):
        user = User.objects.create_user(username=username, email=f"{username}@example.edu", password="pass")
        UserRole.objects.create(user=user, role=role)
        return user

    def _base_record(self, title, publication_type=None):
        publication = create_publication(
            actor=self.student_user,
            owner_student=self.student,
            publication_type=publication_type or self.publication_type,
            title=title,
            abstract="A public-safe abstract.",
            journal_or_conference_name="Portal Journal",
            publication_date=date(2025, 5, 1),
            language="en",
            doi=f"10.9999/{title.lower().replace(' ', '-')}",
        )
        publication.indices.add(self.index)
        publication.research_fields.add(self.field)
        PublicationAuthor.objects.create(
            publication=publication,
            display_name="Public Author",
            affiliation="Fu Jen University",
            author_order=1,
            is_corresponding_author=True,
            linked_user=self.student_user,
        )
        SourceDocument.objects.create(
            publication=publication,
            document_type=SourceDocument.DocumentType.OTHER,
            original_filename="private-evidence.pdf",
            storage_key=f"portal/{publication.id}",
            mime_type="application/pdf",
            file_size=32,
            checksum_sha256=f"{publication.id.int:064x}",
            uploaded_by=self.student_user,
        )
        return publication

    def _approved_record(self, *, title, visibility, published):
        publication = self._base_record(title)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        approve_publication(actor=self.staff, publication_id=publication.id)
        set_visibility(actor=self.staff, publication_id=publication.id, visibility_scope=visibility)
        if published:
            set_published(actor=self.staff, publication_id=publication.id, is_published=True)
        return publication

    def _submitted_public_looking_record(self):
        publication = self._base_record("Submitted public-looking result", self.other_type)
        submit_publication(actor=self.student_user, publication_id=publication.id)
        publication.is_published = True
        publication.visibility_scope = PublicationRecord.VisibilityScope.PUBLIC
        publication.save(update_fields=["is_published", "visibility_scope", "updated_at"])
        return publication

    def test_anonymous_can_only_view_approved_published_public_metadata(self):
        response = self.client.get(reverse("public_site:publication_list"))
        self.assertContains(response, self.public_record.title)
        for private in (self.unpublished, self.submitted, self.department_record, self.owner_advisor, self.staff_only):
            self.assertNotContains(response, private.title)
        self.assertEqual(self.client.get(reverse("public_site:publication_detail", args=[self.public_record.id])).status_code, 200)

    def test_anonymous_direct_uuid_access_cannot_bypass_visibility(self):
        for private in (self.unpublished, self.submitted, self.department_record, self.owner_advisor, self.staff_only):
            self.assertEqual(
                self.client.get(reverse("public_site:publication_detail", args=[private.id])).status_code,
                404,
            )

    def test_department_identity_can_view_department_metadata_but_unauthorized_identity_cannot(self):
        self.client.force_login(self.department_user)
        response = self.client.get(reverse("public_site:department_list"))
        self.assertContains(response, self.public_record.title)
        self.assertContains(response, self.department_record.title)
        self.assertNotContains(response, self.owner_advisor.title)
        self.assertNotContains(response, self.staff_only.title)
        self.assertEqual(
            self.client.get(reverse("public_site:department_detail", args=[self.department_record.id])).status_code,
            200,
        )
        self.client.force_login(self.is_staff_only)
        self.assertEqual(self.client.get(reverse("public_site:department_list")).status_code, 404)

    def test_department_portal_retains_existing_owner_and_staff_object_permissions(self):
        self.client.force_login(self.student_user)
        owner_view = self.client.get(reverse("public_site:department_list"))
        self.assertContains(owner_view, self.owner_advisor.title)
        self.assertNotContains(owner_view, self.staff_only.title)
        self.client.force_login(self.staff)
        staff_view = self.client.get(reverse("public_site:department_list"))
        self.assertContains(staff_view, self.staff_only.title)

    def test_filters_and_search_never_add_private_records_to_public_queryset(self):
        response = self.client.get(reverse("public_site:publication_list"), {
            "year": 2025,
            "publication_type": self.publication_type.id,
            "publication_index": self.index.id,
            "research_field": self.field.id,
            "language": "en",
        })
        self.assertContains(response, self.public_record.title)
        self.assertNotContains(response, self.unpublished.title)
        response = self.client.get(reverse("public_site:publication_list"), {"q": "result"})
        self.assertContains(response, self.public_record.title)
        self.assertNotContains(response, self.owner_advisor.title)
        self.assertNotContains(response, self.submitted.title)

    def test_public_sorting_uses_allowlist(self):
        response = self.client.get(reverse("public_site:publication_list"), {"sort": "title"})
        self.assertEqual(response.context["sort"], "title")
        response = self.client.get(reverse("public_site:publication_list"), {"sort": "owner_student__user__password"})
        self.assertEqual(response.context["sort"], "publication_date")

    def test_public_metadata_never_exposes_source_document_download(self):
        document = self.public_record.documents.get()
        detail = self.client.get(reverse("public_site:publication_detail", args=[self.public_record.id]))
        self.assertNotContains(detail, document.original_filename)
        self.assertNotContains(detail, reverse("documents:download", args=[document.id]))
        self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 302)
        self.client.force_login(self.department_user)
        self.assertEqual(self.client.get(reverse("documents:download", args=[document.id])).status_code, 404)
