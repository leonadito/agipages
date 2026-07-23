import re

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import migrations, models


def backfill_usernames(apps, schema_editor):
    """Derive a username from each existing user's email local-part, so
    real deployed data (VPS) survives the email->username auth switch
    without any manual intervention."""
    User = apps.get_model("accounts", "User")
    used = set(
        User.objects.exclude(username__isnull=True)
        .exclude(username="")
        .values_list("username", flat=True)
    )
    for user in User.objects.filter(
        models.Q(username__isnull=True) | models.Q(username="")
    ):
        local_part = (user.email or "").split("@")[0]
        base = re.sub(r"[^\w.@+-]", "", local_part) or f"usuario{user.pk}"
        base = base[:140]
        candidate = base
        suffix = 1
        while candidate in used:
            suffix += 1
            candidate = f"{base}{suffix}"[:150]
        used.add(candidate)
        user.username = candidate
        user.save(update_fields=["username"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # Step 1: add nullable first, so it's safe on tables with existing rows.
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=150, null=True, blank=True),
        ),
        # Step 2: backfill from email for any pre-existing rows.
        migrations.RunPython(backfill_usernames, noop),
        # Step 3: lock it down to match AbstractUser's real field definition.
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                error_messages={"unique": "A user with that username already exists."},
                help_text=(
                    "Required. 150 characters or fewer. "
                    "Letters, digits and @/./+/-/_ only."
                ),
                max_length=150,
                unique=True,
                validators=[UnicodeUsernameValidator()],
                verbose_name="username",
            ),
        ),
    ]
