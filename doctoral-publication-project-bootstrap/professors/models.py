import uuid
from django.conf import settings
from django.db import models


class Professor(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "有效"
        ARCHIVED = "archived", "封存"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="professor_profile")
    display_name = models.CharField(max_length=200, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        verbose_name = "教授"
        verbose_name_plural = "教授"

    def __str__(self): return self.display_name
