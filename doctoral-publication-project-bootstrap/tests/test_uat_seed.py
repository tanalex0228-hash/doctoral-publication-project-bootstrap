import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from publications.models import PublicationRecord
from publications.querysets import official_publications


class UatSeedCommandTests(TestCase):
    @override_settings(DJANGO_ENV="production")
    def test_seed_refuses_production(self):
        with patch.dict(os.environ, {"UAT_SEED_PASSWORD": "not-used"}):
            with self.assertRaises(CommandError):
                call_command("seed_uat")

    def test_seed_creates_reusable_non_production_demo_data(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            with patch.dict(os.environ, {"UAT_SEED_PASSWORD": "uat-test-password"}):
                call_command("seed_uat")
                call_command("seed_uat")
        self.assertTrue(User.objects.filter(username="uat-student-a").exists())
        self.assertTrue(PublicationRecord.objects.filter(title="UAT I submitted").exists())
        self.assertTrue(PublicationRecord.objects.filter(title="UAT J returned").exists())
        self.assertTrue(PublicationRecord.objects.filter(title="UAT L approved revision").exists())
        self.assertTrue(official_publications().filter(title="UAT G archived official").exists())
        self.assertFalse(official_publications().filter(title="UAT H revoked").exists())
