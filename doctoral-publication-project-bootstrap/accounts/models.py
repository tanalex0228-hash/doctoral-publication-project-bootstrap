import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="uq_user_email_ci")]

    def has_project_role(self, *slugs):
        return self.is_active and self.user_roles.filter(role__slug__in=slugs, role__is_active=True).exists()


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return self.display_name


class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    assigned_at = models.DateTimeField(auto_now_add=True, db_index=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_roles")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="uq_user_role")]
