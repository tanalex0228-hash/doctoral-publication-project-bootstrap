from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from accounts.models import Role, User, UserRole
from accounts.services import IMPORT_HEADERS, import_accounts, parse_account_workbook, replace_user_role
from audit.models import AuditLog
from doctoral_students.models import DoctoralStudentProfile
from doctoral_students.services import bulk_set_enrollment_status
from professors.models import Professor


class BulkAccountManagementTests(TestCase):
    def setUp(self):
        self.roles = {
            slug: Role.objects.create(slug=slug, display_name=slug)
            for slug in ("advisor", "student", "staff", "admin")
        }
        self.root = User.objects.create_superuser(
            username="root", email="root@example.edu", password="pass",
        )
        self.staff = User.objects.create_user(username="staff", email="staff@example.edu", password="pass")
        UserRole.objects.create(user=self.staff, role=self.roles["staff"])
        self.student_actor = User.objects.create_user(username="student-actor", email="student-actor@example.edu", password="pass")
        UserRole.objects.create(user=self.student_actor, role=self.roles["student"])

    def workbook(self, rows, headers=IMPORT_HEADERS):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(headers)
        for row in rows:
            worksheet.append(row)
        stream = BytesIO()
        workbook.save(stream)
        return SimpleUploadedFile("accounts.xlsx", stream.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_bad_headers_are_rejected_without_creating_any_account(self):
        upload = self.workbook([], headers=("姓名", "帳號"))
        with self.assertRaisesMessage(ValidationError, "欄位順序或名稱不符"):
            parse_account_workbook(upload)
        self.assertEqual(User.objects.exclude(pk=self.root.pk).count(), 2)

    def test_any_invalid_row_prevents_partial_import(self):
        upload = self.workbook([
            (1, "學生甲", "student-a@example.edu", "D100", "student", "商學院", "secret", "x", "v", "student", ""),
            (2, "學生乙", "student-b@example.edu", "", "student", "商學院", "secret", "x", "v", "student", "114"),
        ])
        with self.assertRaisesMessage(ValidationError, "學生必須填寫"):
            parse_account_workbook(upload)
        self.assertFalse(User.objects.filter(email="student-a@example.edu").exists())

    def test_import_creates_requested_identity_role_and_optional_admission_year(self):
        upload = self.workbook([
            (1, "學生甲", "student-a@example.edu", 413411539, "student", "商學院", "secret", "x", "v", "student", ""),
            (2, "教師乙", "teacher-b@example.edu", "", "teacher", "商學院", "", "v", "x", "teacher", ""),
            (3, "管理丙", "admin-c@example.edu", "", "admin", "商學院", "admin-pass", "v", "v", "admin", 114),
        ])
        accounts = parse_account_workbook(upload)
        created = import_accounts(actor=self.root, accounts=accounts)
        self.assertEqual(len(created), 3)

        student = User.objects.get(email="student-a@example.edu")
        self.assertEqual(student.username, "學生甲")
        self.assertTrue(student.check_password("secret"))
        self.assertEqual(student.doctoral_profile.student_number, "413411539")
        self.assertIsNone(student.doctoral_profile.admission_year)
        self.assertEqual(student.user_roles.get().role.slug, "student")

        teacher = User.objects.get(email="teacher-b@example.edu")
        self.assertTrue(teacher.is_staff)
        self.assertFalse(teacher.has_usable_password())
        self.assertEqual(teacher.professor_profile.display_name, "教師乙")
        self.assertEqual(teacher.user_roles.get().role.slug, "advisor")

        admin = User.objects.get(email="admin-c@example.edu")
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.doctoral_profile if hasattr(admin, "doctoral_profile") else None, None)
        self.assertEqual(admin.user_roles.get().role.slug, "admin")
        self.assertEqual(AuditLog.objects.filter(action="account.bulk_imported").count(), 3)

    def test_only_root_or_project_admin_can_import_and_change_roles(self):
        account = parse_account_workbook(self.workbook([
            (1, "學生甲", "student-a@example.edu", "D100", "student", "商學院", "secret", "x", "v", "student", "114"),
        ]))[0]
        with self.assertRaises(PermissionDenied):
            import_accounts(actor=self.staff, accounts=[account])
        target = User.objects.create_user(username="target", email="target@example.edu", password="pass")
        UserRole.objects.create(user=target, role=self.roles["student"])
        with self.assertRaises(PermissionDenied):
            replace_user_role(actor=self.staff, user=target, role_slug="admin")
        replace_user_role(actor=self.root, user=target, role_slug="advisor")
        self.assertEqual(list(target.user_roles.values_list("role__slug", flat=True)), ["advisor"])
        self.assertTrue(AuditLog.objects.filter(action="account.role_replaced", target_id=target.pk).exists())

    def test_staff_can_batch_change_enrollment_status_with_audit(self):
        student = User.objects.create_user(username="student-bulk", email="student-bulk@example.edu", password="pass")
        UserRole.objects.create(user=student, role=self.roles["student"])
        profile = DoctoralStudentProfile.objects.create(
            user=student, student_number="D200", display_name="學生學籍", admission_year=None,
        )
        changed = bulk_set_enrollment_status(
            actor=self.staff, profiles=DoctoralStudentProfile.objects.filter(pk=profile.pk),
            enrollment_status=DoctoralStudentProfile.EnrollmentStatus.GRADUATED,
        )
        profile.refresh_from_db()
        self.assertEqual(changed, 1)
        self.assertEqual(profile.enrollment_status, DoctoralStudentProfile.EnrollmentStatus.GRADUATED)
        self.assertTrue(AuditLog.objects.filter(action="student_profile.enrollment_status_changed", target_id=profile.pk).exists())
        with self.assertRaises(PermissionDenied):
            bulk_set_enrollment_status(
                actor=self.student_actor, profiles=DoctoralStudentProfile.objects.filter(pk=profile.pk),
                enrollment_status=DoctoralStudentProfile.EnrollmentStatus.ACTIVE,
            )
