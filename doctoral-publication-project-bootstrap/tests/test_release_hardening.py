from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User, UserRole
from advising.models import StudentAdvisor
from professors.models import Professor
from tests.test_core_contract import ContractFixture


class HealthAndSecurityTests(TestCase):
    def test_healthz_confirms_database_connection_and_security_headers(self):
        with patch("config.views.connection.ensure_connection") as ensure_connection:
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})
        ensure_connection.assert_called_once()
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_healthz_returns_non_disclosing_503_when_database_is_unavailable(self):
        with patch("config.views.connection.ensure_connection", side_effect=DatabaseError("connection refused")):
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 503)
        self.assertJSONEqual(response.content, {"status": "unavailable"})
        self.assertNotIn("connection refused", response.content.decode())

    def test_postgresql_remains_the_only_configured_database_backend(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertTrue(settings.DATABASES["default"]["TEST"]["NAME"].startswith("test_"))


class RoleMatrixRegressionTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.admin_role = Role.objects.create(slug="admin", display_name="Admin")
        self.admin_user = self.user("release-admin", self.admin_role)
        self.advisor_user = self.user("release-advisor", self.advisor_role)
        self.advisor = Professor.objects.create(user=self.advisor_user, display_name="Release Advisor")
        StudentAdvisor.objects.create(student=self.student, professor=self.advisor)
        self.django_staff_only = User.objects.create_user(
            username="release-django-staff",
            email="release-django-staff@example.edu",
            password="pass",
            is_staff=True,
        )
        self.multi_role_user = self.user("release-multi-role", self.student_role)
        UserRole.objects.create(user=self.multi_role_user, role=self.advisor_role)

    def test_staff_admin_and_non_business_staff_boundaries(self):
        staff_resources = ("review:queue", "review:archive_list", "statistics:dashboard")
        for user in (self.staff, self.admin_user):
            self.client.force_login(user)
            for resource in staff_resources:
                self.assertEqual(self.client.get(reverse(resource)).status_code, 200)

        for user in (self.student_user, self.advisor_user, self.django_staff_only, self.multi_role_user):
            self.client.force_login(user)
            for resource in staff_resources:
                self.assertEqual(self.client.get(reverse(resource)).status_code, 404)

    def test_department_and_advisor_boundaries_remain_role_and_object_scoped(self):
        self.assertEqual(self.client.get(reverse("public_site:publication_list")).status_code, 200)

        for user in (self.student_user, self.advisor_user, self.staff, self.admin_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("public_site:department_list")).status_code, 200)

        self.client.force_login(self.django_staff_only)
        self.assertEqual(self.client.get(reverse("public_site:department_list")).status_code, 404)

        self.client.force_login(self.advisor_user)
        self.assertEqual(self.client.get(reverse("dashboard:advisor")).status_code, 200)
        self.client.force_login(self.multi_role_user)
        self.assertEqual(self.client.get(reverse("dashboard:advisor")).status_code, 404)
