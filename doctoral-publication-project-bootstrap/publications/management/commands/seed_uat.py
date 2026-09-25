"""Create a deterministic, non-production UAT dataset."""

import os
from datetime import date, timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User, UserRole
from advising.models import StudentAdvisor
from documents.services import upload_document
from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from publications.models import PublicationAuthor, PublicationRecord
from publications.services import create_publication, create_revision, set_published, set_visibility, submit_publication, update_publication
from review.services import approve_publication, archive_publication, return_for_revision, revoke_approval
from taxonomy.models import PublicationIndex, PublicationType, ResearchField


class Command(BaseCommand):
    help = "Seed deterministic UAT accounts and publications. Refuses DJANGO_ENV=production."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password-env",
            default="UAT_SEED_PASSWORD",
            help="Environment variable containing the UAT account password (default: UAT_SEED_PASSWORD).",
        )

    def handle(self, *args, **options):
        if settings.DJANGO_ENV == "production":
            raise CommandError("seed_uat is forbidden when DJANGO_ENV=production.")
        password = os.environ.get(options["password_env"])
        if not password:
            raise CommandError(f"Set {options['password_env']} to a non-production UAT password before seeding.")
        with transaction.atomic():
            self._seed(password)
        self.stdout.write(self.style.SUCCESS("UAT seed is ready. Re-running this command is idempotent."))

    def _user(self, username, password, roles=(), *, staff=False, superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@uat.example.invalid", "is_staff": staff, "is_superuser": superuser},
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        for role in roles:
            UserRole.objects.get_or_create(user=user, role=role)
        return user

    def _publication(self, *, owner, actor, publication_type, title, visibility, published=True):
        publication = PublicationRecord.objects.filter(owner_student=owner, title=title).first()
        if publication:
            return publication
        publication = create_publication(
            actor=actor, owner_student=owner, publication_type=publication_type,
            title=title, abstract="Synthetic UAT evidence only.",
            journal_or_conference_name="UAT Journal", language="en",
            publication_date=date(2025, 1, 15),
        )
        PublicationAuthor.objects.create(
            publication=publication, display_name=owner.display_name, author_order=1,
            linked_user=owner.user, is_corresponding_author=True,
        )
        upload_document(
            actor=actor,
            publication=publication,
            upload=SimpleUploadedFile("uat-evidence.pdf", b"%PDF-1.4 UAT synthetic evidence", content_type="application/pdf"),
        )
        submit_publication(actor=actor, publication_id=publication.id)
        approve_publication(actor=self.staff, publication_id=publication.id)
        set_visibility(actor=self.staff, publication_id=publication.id, visibility_scope=visibility)
        set_published(actor=self.staff, publication_id=publication.id, is_published=published)
        publication.refresh_from_db()
        return publication

    def _seed(self, password):
        roles = {
            slug: Role.objects.get_or_create(slug=slug, defaults={"display_name": slug.title()})[0]
            for slug in ("student", "advisor", "staff", "admin")
        }
        self.student_a_user = self._user("uat-student-a", password, [roles["student"]])
        student_b_user = self._user("uat-student-b", password, [roles["student"]])
        graduated_user = self._user("uat-graduated", password, [roles["student"]])
        advisor_a_user = self._user("uat-advisor-a", password, [roles["advisor"]])
        advisor_b_user = self._user("uat-advisor-b", password, [roles["advisor"]])
        self.staff = self._user("uat-secretary", password, [roles["staff"]])
        self._user("uat-admin", password, [roles["admin"]], staff=True, superuser=True)
        self._user("uat-django-staff-only", password, staff=True)
        multi_user = self._user("uat-multi-role", password, [roles["student"], roles["advisor"]])

        field, _ = ResearchField.objects.get_or_create(slug="uat-management", defaults={"display_name": "UAT Management"})
        publication_type, _ = PublicationType.objects.get_or_create(slug="uat-journal", defaults={"display_name": "UAT Journal"})
        publication_index, _ = PublicationIndex.objects.get_or_create(slug="uat-index", defaults={"display_name": "UAT Index"})
        student_a, _ = DoctoralStudentProfile.objects.get_or_create(
            user=self.student_a_user,
            defaults={"student_number": "UAT-A", "display_name": "UAT Current Student A", "admission_year": 114, "primary_field": field},
        )
        student_b, _ = DoctoralStudentProfile.objects.get_or_create(
            user=student_b_user,
            defaults={"student_number": "UAT-B", "display_name": "UAT Current Student B", "admission_year": 114, "primary_field": field},
        )
        graduated, _ = DoctoralStudentProfile.objects.get_or_create(
            user=graduated_user,
            defaults={"student_number": "UAT-G", "display_name": "UAT Graduated Student", "admission_year": 108, "enrollment_status": DoctoralStudentProfile.EnrollmentStatus.GRADUATED, "primary_field": field},
        )
        advisor_a, _ = Professor.objects.get_or_create(user=advisor_a_user, defaults={"display_name": "UAT Advisor A"})
        advisor_b, _ = Professor.objects.get_or_create(user=advisor_b_user, defaults={"display_name": "UAT Advisor B"})
        Professor.objects.get_or_create(user=multi_user, defaults={"display_name": "UAT Multi-role Professor"})
        StudentAdvisor.objects.get_or_create(student=student_a, professor=advisor_a, defaults={"end_date": date.today() - timedelta(days=30), "is_active": True})
        StudentAdvisor.objects.get_or_create(student=student_a, professor=advisor_b, defaults={"is_active": False})
        StudentAdvisor.objects.get_or_create(student=student_b, professor=advisor_b, defaults={"is_active": True})

        scopes = PublicationRecord.VisibilityScope
        publications = {
            "A": self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT A approved public", visibility=scopes.PUBLIC),
            "B": self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT B approved department all", visibility=scopes.DEPARTMENT_ALL),
            "C": self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT C approved department current", visibility=scopes.DEPARTMENT_CURRENT),
            "D": self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT D approved owner faculty", visibility=scopes.OWNER_FACULTY),
            "E": self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT E approved owner advisor", visibility=scopes.OWNER_ADVISOR),
            "F": self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT F approved staff only", visibility=scopes.STAFF_ONLY),
        }
        for publication in publications.values():
            publication.indices.add(publication_index)
            publication.research_fields.add(field)
        archived = self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT G archived official", visibility=scopes.PUBLIC)
        if archived.workflow_status == PublicationRecord.WorkflowStatus.APPROVED:
            archive_publication(actor=self.staff, publication_id=archived.id, reason="UAT archive")
        revoked = self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT H revoked", visibility=scopes.PUBLIC)
        if revoked.workflow_status == PublicationRecord.WorkflowStatus.APPROVED:
            revoke_approval(actor=self.staff, publication_id=revoked.id, reason="UAT revocation")

        submitted = PublicationRecord.objects.filter(owner_student=student_a, title="UAT I submitted").first()
        if not submitted:
            submitted = create_publication(actor=self.student_a_user, owner_student=student_a, publication_type=publication_type, title="UAT I submitted")
            PublicationAuthor.objects.create(publication=submitted, display_name=student_a.display_name, author_order=1)
            upload_document(actor=self.student_a_user, publication=submitted, upload=SimpleUploadedFile("uat-submitted.pdf", b"%PDF-1.4 submitted", content_type="application/pdf"))
            submit_publication(actor=self.student_a_user, publication_id=submitted.id)
        returned = PublicationRecord.objects.filter(owner_student=student_a, title="UAT J returned").first()
        if not returned:
            returned = create_publication(actor=self.student_a_user, owner_student=student_a, publication_type=publication_type, title="UAT J returned")
            PublicationAuthor.objects.create(publication=returned, display_name=student_a.display_name, author_order=1)
            upload_document(actor=self.student_a_user, publication=returned, upload=SimpleUploadedFile("uat-returned.pdf", b"%PDF-1.4 returned", content_type="application/pdf"))
            submit_publication(actor=self.student_a_user, publication_id=returned.id)
            return_for_revision(actor=self.staff, publication_id=returned.id, reason="UAT return")

        pending_original = self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT K official with pending revision", visibility=scopes.PUBLIC)
        if not pending_original.series.versions.filter(is_revision=True).exists():
            revision = create_revision(actor=self.student_a_user, publication_id=pending_original.id)
            update_publication(
                actor=self.student_a_user,
                publication_id=revision.id,
                title="UAT K pending revision",
                publication_type=publication_type,
                indices=pending_original.indices.all(),
                research_fields=pending_original.research_fields.all(),
            )
            submit_publication(actor=self.student_a_user, publication_id=revision.id)
        replaced_original = self._publication(owner=student_a, actor=self.student_a_user, publication_type=publication_type, title="UAT L old official", visibility=scopes.PUBLIC)
        if replaced_original.series.current_official_version_id == replaced_original.id and not replaced_original.series.versions.filter(is_revision=True).exists():
            revision = create_revision(actor=self.student_a_user, publication_id=replaced_original.id)
            update_publication(
                actor=self.student_a_user,
                publication_id=revision.id,
                title="UAT L approved revision",
                publication_type=publication_type,
                indices=replaced_original.indices.all(),
                research_fields=replaced_original.research_fields.all(),
            )
            submit_publication(actor=self.student_a_user, publication_id=revision.id)
            approve_publication(actor=self.staff, publication_id=revision.id)
