from django.test import TestCase
from django.urls import reverse

from publications.services import create_publication
from tests.test_core_contract import ContractFixture


class AccountSelfServiceTests(ContractFixture):
    def test_profile_requires_login_and_only_shows_own_publications(self):
        mine = self.publication()
        other = create_publication(
            actor=self.other_student_user,
            owner_student=self.other_student,
            publication_type=self.type,
            title="Other student's private publication",
        )
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, mine.title)
        self.assertNotContains(response, other.title)
        self.assertContains(response, reverse("accounts:password_change"))

    def test_password_change_keeps_current_user_logged_in(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "pass",
            "new_password1": "A-new-test-password-902!",
            "new_password2": "A-new-test-password-902!",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password("A-new-test-password-902!"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
