import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def create_series_and_reconcile_department(apps, schema_editor):
    PublicationRecord = apps.get_model("publications", "PublicationRecord")
    PublicationSeries = apps.get_model("publications", "PublicationSeries")

    for publication in PublicationRecord.objects.order_by("created_at").iterator():
        series = PublicationSeries.objects.create(owner_student_id=publication.owner_student_id)
        PublicationRecord.objects.filter(pk=publication.pk).update(series_id=series.pk)
        if publication.workflow_status in {"approved", "archived"}:
            PublicationSeries.objects.filter(pk=series.pk).update(current_official_version_id=publication.pk)

    PublicationRecord.objects.filter(visibility_scope="department").update(
        visibility_scope="department_all"
    )


def restore_legacy_department(apps, schema_editor):
    PublicationRecord = apps.get_model("publications", "PublicationRecord")
    # Only the deterministic legacy mapping can be reversed. New scopes remain
    # intact so a rollback does not silently discard post-migration policy data.
    PublicationRecord.objects.filter(visibility_scope="department_all").update(
        visibility_scope="department"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("publications", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicationSeries",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "current_official_version",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="current_for_series", to="publications.publicationrecord"),
                ),
                (
                    "owner_student",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="publication_series", to="doctoral_students.doctoralstudentprofile"),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["owner_student", "current_official_version"], name="idx_series_official")],
            },
        ),
        migrations.AddField(
            model_name="publicationrecord",
            name="series",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="publications.publicationseries"),
        ),
        migrations.AddField(
            model_name="publicationrecord",
            name="is_revision",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="publicationrecord",
            name="approval_revoked_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="publicationrecord",
            name="approval_revoked_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="revoked_publications", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="publicationrecord",
            name="workflow_status",
            field=models.CharField(choices=[("draft", "草稿"), ("submitted", "已送審"), ("returned", "已退回"), ("approved", "已核准"), ("archived", "已封存"), ("withdrawn", "已撤回"), ("revoked", "已撤銷核准")], db_index=True, default="draft", max_length=16),
        ),
        migrations.AlterField(
            model_name="publicationrecord",
            name="visibility_scope",
            field=models.CharField(choices=[("public", "公開"), ("department_all", "系所全體"), ("department_current", "系所在學"), ("owner_faculty", "本人與全體教職員"), ("owner_advisor", "本人與指導教授"), ("staff_only", "工作人員限定")], db_index=True, default="owner_advisor", max_length=24),
        ),
        migrations.RunPython(create_series_and_reconcile_department, restore_legacy_department),
        migrations.AlterField(
            model_name="publicationrecord",
            name="series",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="publications.publicationseries"),
        ),
        migrations.AddIndex(
            model_name="publicationrecord",
            index=models.Index(fields=["series", "workflow_status"], name="idx_series_status"),
        ),
        migrations.AddConstraint(
            model_name="publicationrecord",
            constraint=models.UniqueConstraint(condition=Q(("is_revision", True), ("workflow_status__in", ["draft", "submitted", "returned"])), fields=("series",), name="uq_pending_revision_series"),
        ),
    ]
