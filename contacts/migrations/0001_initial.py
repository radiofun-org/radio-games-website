import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Callsign",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("callsign", models.TextField(unique=True)),
            ],
            options={"db_table": "matcher_callsign"},
        ),
        migrations.CreateModel(
            name="AdifMetadata",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("process_time", models.BigIntegerField()),
                ("file_hash", models.TextField(unique=True)),
                ("adif_version", models.TextField(default="")),
                ("program_id", models.TextField(default="")),
                ("program_version", models.TextField(default="")),
            ],
            options={"db_table": "matcher_adif_metadata"},
        ),
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("adif_metadata_id", models.BigIntegerField(null=True)),
                ("date", models.SmallIntegerField()),
                ("time", models.SmallIntegerField()),
                ("time_off", models.SmallIntegerField()),
                ("from_id", models.BigIntegerField()),
                ("to_id", models.BigIntegerField()),
                ("band", models.SmallIntegerField()),
                ("mode", models.SmallIntegerField()),
                ("sub_mode", models.SmallIntegerField()),
                ("grid", models.BigIntegerField()),
                ("grid_size", models.SmallIntegerField()),
                ("administrative_primary", models.TextField(default="")),
                ("administrative_secondary", models.TextField(default="")),
                ("dxcc", models.SmallIntegerField()),
                ("zone_cq", models.SmallIntegerField()),
                ("zone_itu", models.SmallIntegerField()),
                ("tx_power", models.SmallIntegerField()),
                (
                    "my_pota",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.TextField(), default=list
                    ),
                ),
                ("my_sota", models.TextField(default="")),
                ("my_wwff", models.TextField(default="")),
                ("my_iota", models.TextField(default="")),
                ("my_sig", models.TextField(default="")),
                ("my_sig_info", models.TextField(default="")),
            ],
            options={
                "db_table": "matcher_contact",
                "unique_together": {("to_id", "date", "time", "from_id")},
            },
        ),
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
                "db_table": "matcher_match",
                "unique_together": {("a_id", "b_id")},
            },
        ),
    ]
