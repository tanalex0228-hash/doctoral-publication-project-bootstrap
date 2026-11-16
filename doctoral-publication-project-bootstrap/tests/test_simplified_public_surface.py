from django.test import SimpleTestCase
from django.urls import reverse


class SimplifiedPublicSurfaceTests(SimpleTestCase):
    def test_public_and_department_portals_are_not_available(self):
        self.assertEqual(self.client.get(reverse("public_site:publication_list")).status_code, 404)
        self.assertEqual(self.client.get(reverse("public_site:department_list")).status_code, 404)
