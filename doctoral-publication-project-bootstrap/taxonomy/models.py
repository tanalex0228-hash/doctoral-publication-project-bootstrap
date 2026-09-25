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


class PublicationType(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name = "成果類型"
        verbose_name_plural = "成果類型"


class PublicationIndex(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name = "成果索引"
        verbose_name_plural = "成果索引"


class ResearchField(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name = "研究領域"
        verbose_name_plural = "研究領域"
