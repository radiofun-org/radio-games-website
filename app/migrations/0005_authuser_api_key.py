from django.db import migrations, models

import app.models


def populate_api_keys(apps, schema_editor):
    AuthUser = apps.get_model("app", "AuthUser")
    for user in AuthUser.objects.all():
        user.api_key = app.models.generate_api_key()
        user.save(update_fields=["api_key"])


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0004_callsignassociation_country_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="authuser",
            name="api_key",
            field=models.CharField(default=app.models.generate_api_key, max_length=64),
        ),
        migrations.RunPython(populate_api_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="authuser",
            name="api_key",
            field=models.CharField(
                default=app.models.generate_api_key, max_length=64, unique=True
            ),
        ),
    ]
