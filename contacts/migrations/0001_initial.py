# Replaces the original unmanaged Match model with a managed one.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Match",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("matched_at", models.BigIntegerField()),
                ("a_id", models.BigIntegerField()),
                ("b_id", models.BigIntegerField()),
                ("a_call_id", models.BigIntegerField()),
                ("b_call_id", models.BigIntegerField()),
            ],
            options={
                "db_table": "matches",
                "unique_together": {("a_id", "b_id")},
            },
        ),
    ]
