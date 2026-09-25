import uuid
from django.db import models


class TaxonomyBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    display_name = models.CharField(max_length=150, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.SmallIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["display_order", "display_name"]

    def __str__(self):
        return self.display_name


class PublicationType(TaxonomyBase): pass
class PublicationIndex(TaxonomyBase): pass
class ResearchField(TaxonomyBase): pass
