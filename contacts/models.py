from django.db import models


class Match(models.Model):
    class Meta:
        db_table = "matches"

    id = models.IntegerField(primary_key=True)

    matched_at = models.IntegerField()

    a_id = models.IntegerField()
    b_id = models.IntegerField()

    a_call_id = models.IntegerField()
    b_call_id = models.IntegerField()
