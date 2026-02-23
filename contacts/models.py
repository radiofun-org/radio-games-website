from django.contrib.postgres.fields import ArrayField
from django.db import models


class Contact(models.Model):
    class Meta:
        db_table = "contacts"
        unique_together = [("to_id", "date", "time", "from_id")]

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
        db_table = "matches"
        unique_together = [("a_id", "b_id")]

    id = models.BigAutoField(primary_key=True)

    matched_at = models.BigIntegerField()

    a_id = models.BigIntegerField()
    b_id = models.BigIntegerField()

    a_call_id = models.BigIntegerField()
    b_call_id = models.BigIntegerField()
