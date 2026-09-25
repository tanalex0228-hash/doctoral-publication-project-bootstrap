import uuid
from django.core.exceptions import ValidationError
from django.db import models


class StudentAdvisor(models.Model):
    class AdvisorRole(models.TextChoices):
        PRIMARY = "primary", "主指導"
        CO_ADVISOR = "co_advisor", "共同指導"
        OTHER = "other", "其他"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("doctoral_students.DoctoralStudentProfile", on_delete=models.PROTECT, related_name="advisor_relations")
    professor = models.ForeignKey("professors.Professor", on_delete=models.PROTECT, related_name="student_relations")
    advisor_role = models.CharField(max_length=16, choices=AdvisorRole.choices, default=AdvisorRole.PRIMARY, db_index=True)
    start_date = models.DateField(null=True, blank=True, db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["student", "is_active"], name="idx_student_active")]
        verbose_name = "學生指導關係"
        verbose_name_plural = "學生指導關係"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Advisor end date cannot precede start date.")
