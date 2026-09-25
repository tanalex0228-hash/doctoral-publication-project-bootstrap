import uuid
from django.conf import settings
from django.db import models


class DoctoralStudentProfile(models.Model):
    class EnrollmentStatus(models.TextChoices):
        ACTIVE = "active", "在學"
        LEAVE = "leave", "休學"
        GRADUATED = "graduated", "畢業"
        WITHDRAWN = "withdrawn", "退學"
        ARCHIVED = "archived", "封存"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="doctoral_profile")
    student_number = models.CharField(max_length=50, unique=True, db_index=True)
    display_name = models.CharField(max_length=200, db_index=True)
    admission_year = models.PositiveSmallIntegerField(db_index=True)
    enrollment_status = models.CharField(max_length=16, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE, db_index=True)
    primary_field = models.ForeignKey("taxonomy.ResearchField", on_delete=models.PROTECT, null=True, blank=True, related_name="primary_students")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "博士生"
        verbose_name_plural = "博士生"

    def __str__(self): return f"{self.student_number} {self.display_name}"
