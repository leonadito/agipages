import uuid

from django.db import migrations, models


def fill(apps, schema_editor):
    LandingPage = apps.get_model("landingpages", "LandingPage")
    for page in LandingPage.objects.filter(uuid__isnull=True):
        page.uuid = uuid.uuid4()
        page.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    """Public uuid in three steps: a single AddField with a default would give
    every existing row the same value and break the unique constraint."""

    dependencies = [("landingpages", "0010_landingpage_lead_notification_emails")]

    operations = [
        migrations.AddField("landingpage", "uuid", models.UUIDField("id público", null=True, editable=False)),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AlterField(
            "landingpage", "uuid",
            models.UUIDField("id público", default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
