from django.conf import settings
from django.db import models


class AwardDefinition(models.Model):
    """An award that users can earn. Defines criteria and evaluation method."""

    class Tier(models.IntegerChoices):
        QUERY = 1, "Query (structured rule)"
        CODE = 2, "Code (Python evaluator)"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=40, db_index=True)
    tier = models.SmallIntegerField(choices=Tier.choices)

    # For tier=QUERY: a structured JSON rule interpreted by the generic evaluator.
    # For tier=CODE: a dotted Python path to an evaluator function.
    evaluator = models.JSONField()

    icon = models.CharField(max_length=200, blank=True, default="")
    sort_order = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class AwardGrant(models.Model):
    """A specific award earned by a specific user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="award_grants"
    )
    award = models.ForeignKey(AwardDefinition, on_delete=models.CASCADE, related_name="grants")

    # When the system determined this was earned (processing time).
    granted_at = models.DateTimeField(auto_now_add=True)

    # The actual date of the qualifying contact — the moment they "really" earned it.
    evidence_at = models.DateTimeField(null=True, blank=True)

    # If a match is later invalidated.
    revoked_at = models.DateTimeField(null=True, blank=True)

    # Were all contributing contacts from verified users?
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "award"],
                condition=models.Q(revoked_at__isnull=True),
                name="one_active_grant_per_user_award",
            ),
        ]
        indexes = [
            models.Index(fields=["award", "granted_at"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.award}"


class AwardProgress(models.Model):
    """Cached progress toward an award for fast display."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="award_progress"
    )
    award = models.ForeignKey(AwardDefinition, on_delete=models.CASCADE, related_name="progress")

    # Flexible progress data — shape depends on award type.
    # e.g. {"count": 87, "needed": 100}
    # e.g. {"worked": ["NA", "EU", "AS"], "needed": ["AF", "OC", "SA"]}
    detail = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "award"], name="one_progress_per_user_award"),
        ]

    def __str__(self):
        return f"{self.user} — {self.award} progress"
