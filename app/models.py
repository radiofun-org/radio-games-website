from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class LogUpload(models.Model):
    log_file = models.FileField(upload_to="uploads/%Y/%m/")
    callsign = models.CharField(max_length=16, default="")
    processed = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    upload_time = models.DateTimeField(auto_now_add=True)


class CallsignAssociation(models.Model):
    callsign = models.CharField(max_length=16)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verified = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    grid_square = models.CharField(max_length=8, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["callsign", "user"], name="unique_callsign_per_user"),
        ]


class AuthUser(AbstractUser):

    class Meta(AbstractUser.Meta):
        # use the same table that Django's built-in user would use; this makes
        # life easier for us
        db_table = "auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
