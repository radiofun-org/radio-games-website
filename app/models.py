import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


def generate_api_key():
    return secrets.token_hex(32)


class LogUpload(models.Model):
    log_file = models.FileField(upload_to="uploads/%Y/%m/")
    callsign = models.CharField(max_length=16, default="")
    processed = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    upload_time = models.DateTimeField(auto_now_add=True)
    # The upload this one corrects ("re-upload this log"). The matcher diffs
    # the two files and deletes contacts the old file asserted that the new
    # one doesn't.
    replaces = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by"
    )


class CallsignAssociation(models.Model):
    callsign = models.CharField(max_length=16)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verified = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    grid_square = models.CharField(max_length=8, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["callsign", "user"], name="unique_callsign_per_user"),
        ]


class AuthUser(AbstractUser):
    api_key = models.CharField(max_length=64, unique=True, default=generate_api_key)

    class Meta(AbstractUser.Meta):
        # use the same table that Django's built-in user would use; this makes
        # life easier for us
        db_table = "auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
