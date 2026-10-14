import uuid

from django.db import migrations, models


def fill(apps, schema_editor):
    Lead = apps.get_model("leads", "Lead")
    for lead in Lead.objects.filter(uuid__isnull=True):
        lead.uuid = uuid.uuid4()
        lead.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    """Public uuid in three steps (see landingpages 0011) plus the fields that
    track the delivery to metaleads."""

    dependencies = [("leads", "0003_lead_extra_field_values_alter_lead_email_and_more")]

    operations = [
        migrations.AddField("lead", "uuid", models.UUIDField("id público", null=True, editable=False)),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AlterField(
            "lead", "uuid", models.UUIDField("id público", default=uuid.uuid4, unique=True, editable=False)
        ),
        migrations.AddField("lead", "metaleads_lead_uuid", models.UUIDField("lead no metaleads", null=True, blank=True)),
        migrations.AddField("lead", "metaleads_sent_at", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("lead", "metaleads_attempts", models.PositiveSmallIntegerField(default=0)),
        migrations.AddField("lead", "metaleads_error", models.TextField(blank=True)),
    ]
