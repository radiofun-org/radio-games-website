from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class LogUpload(models.Model):
    log_file = models.FileField()
    processed = models.BooleanField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    upload_time = models.DateTimeField(auto_now_add=True)


class CallsignAssociation(models.Model):
    callsign = models.CharField(max_length=16)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verified = models.BooleanField()


class AuthUser(AbstractUser):

    class Meta:
        # use the same table that Django's built-in user would use; this makes
        # life easier for us
        db_table = "auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
