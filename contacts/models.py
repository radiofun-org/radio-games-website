from django.contrib.postgres.fields import ArrayField
from django.db import models


class Callsign(models.Model):
    class Meta:
        db_table = "matcher_callsign"

    id = models.BigAutoField(primary_key=True)
    callsign = models.TextField(unique=True)

    def __str__(self):
        return self.callsign


class AdifMetadata(models.Model):
    class Meta:
        db_table = "matcher_adif_metadata"

    id = models.BigAutoField(primary_key=True)
    process_time = models.BigIntegerField()
    file_hash = models.TextField(unique=True)
    adif_version = models.TextField(default="")
    program_id = models.TextField(default="")
    program_version = models.TextField(default="")


class Contact(models.Model):
    class Meta:
        db_table = "matcher_contact"
        unique_together = [("to_id", "date", "time", "from_id")]
        indexes = [
            # Profile stats, logbook, and public callsign pages all query by
            # the sending station; the unique index only covers to_id.
            models.Index(fields=["from_id"], name="matcher_contact_from_id"),
        ]

    id = models.BigAutoField(primary_key=True)
    adif_metadata_id = models.BigIntegerField(null=True)
    date = models.SmallIntegerField()
    time = models.SmallIntegerField()
    time_off = models.SmallIntegerField()
    from_id = models.BigIntegerField()
    to_id = models.BigIntegerField()
    band = models.SmallIntegerField()
    mode = models.SmallIntegerField()
    sub_mode = models.SmallIntegerField()
    grid = models.BigIntegerField()
    grid_size = models.SmallIntegerField()
    administrative_primary = models.TextField(default="")
    administrative_secondary = models.TextField(default="")
    dxcc = models.SmallIntegerField()
    zone_cq = models.SmallIntegerField()
    zone_itu = models.SmallIntegerField()
    tx_power = models.SmallIntegerField()
    my_pota = ArrayField(models.TextField(), default=list)
    my_sota = models.TextField(default="")
    my_wwff = models.TextField(default="")
    my_iota = models.TextField(default="")
    my_sig = models.TextField(default="")
    my_sig_info = models.TextField(default="")


class Match(models.Model):
    class Meta:
        db_table = "matcher_match"
        unique_together = [("a_id", "b_id")]
        indexes = [
            # Match lookups always OR both sides (a and b); the unique index
            # only covers a_id, so each side needs its own index for Postgres
            # to combine them. matched_at serves API cursor pagination and
            # the incremental ADIF export's `since` filter.
            models.Index(fields=["b_id"], name="matcher_match_b_id"),
            models.Index(fields=["a_call_id"], name="matcher_match_a_call_id"),
            models.Index(fields=["b_call_id"], name="matcher_match_b_call_id"),
            models.Index(fields=["matched_at"], name="matcher_match_matched_at"),
        ]

    id = models.BigAutoField(primary_key=True)

    matched_at = models.BigIntegerField()

    a_id = models.BigIntegerField()
    b_id = models.BigIntegerField()

    a_call_id = models.BigIntegerField()
    b_call_id = models.BigIntegerField()
