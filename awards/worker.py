"""Awards evaluation worker.

Pops callsign IDs from the Redis set `awards_eval_pending`, resolves them to
users via CallsignAssociation, and evaluates all enabled awards for each user.
"""

import logging


from app.models import CallsignAssociation
from contacts.models import Callsign

from .evaluate import (
    EvalResult,
    evaluate_code_award,
    evaluate_query_award,
    get_confirmed_contacts,
)
from .models import AwardDefinition, AwardGrant, AwardProgress

logger = logging.getLogger(__name__)


def resolve_users_for_callsign_ids(callsign_ids: list[int]) -> dict[int, list[int]]:
    """Map callsign IDs → user IDs via Callsign → CallsignAssociation.

    Returns {user_id: [matcher_callsign_id, ...]}.
    """
    # Resolve integer IDs to callsign strings
    id_to_call = dict(Callsign.objects.filter(id__in=callsign_ids).values_list("id", "callsign"))

    if not id_to_call:
        return {}

    # Find all associations for these callsigns
    # (ignoring date filtering for now — evaluate all time periods)
    assocs = CallsignAssociation.objects.filter(callsign__in=id_to_call.values()).values_list(
        "callsign", "user_id"
    )

    # Build reverse map: callsign string → matcher ID
    call_to_ids: dict[str, list[int]] = {}
    for mid, call_str in id_to_call.items():
        call_to_ids.setdefault(call_str, []).append(mid)

    # Build user → matcher IDs
    user_matcher_ids: dict[int, list[int]] = {}
    for call_str, user_id in assocs:
        for mid in call_to_ids.get(call_str, []):
            user_matcher_ids.setdefault(user_id, []).append(mid)

    return user_matcher_ids


def get_all_matcher_ids_for_user(user_id: int) -> list[int]:
    """Get ALL matcher callsign IDs for a user (not just the ones that triggered)."""
    user_calls = list(
        CallsignAssociation.objects.filter(user_id=user_id).values_list("callsign", flat=True)
    )
    if not user_calls:
        return []
    return list(Callsign.objects.filter(callsign__in=user_calls).values_list("id", flat=True))


def evaluate_user(user_id: int):
    """Evaluate all enabled awards for a single user."""
    matcher_ids = get_all_matcher_ids_for_user(user_id)
    if not matcher_ids:
        return

    # Fetch confirmed contacts once — shared across all award evaluations
    confirmed = get_confirmed_contacts(matcher_ids)

    awards = AwardDefinition.objects.filter(enabled=True)

    for award in awards:
        try:
            result = _evaluate_single(award, confirmed, matcher_ids)
        except Exception:
            logger.exception("Error evaluating award %s for user %d", award.slug, user_id)
            continue

        # Update progress
        AwardProgress.objects.update_or_create(
            user_id=user_id,
            award=award,
            defaults={"detail": result.progress},
        )

        # Grant if newly earned
        if result.earned:
            _maybe_grant(user_id, award, result)


def _evaluate_single(
    award: AwardDefinition,
    confirmed: list,
    matcher_ids: list[int],
) -> EvalResult:
    """Evaluate a single award definition."""
    if award.tier == AwardDefinition.Tier.QUERY:
        return evaluate_query_award(confirmed, award.evaluator)
    elif award.tier == AwardDefinition.Tier.CODE:
        path = award.evaluator.get("path", "")
        return evaluate_code_award(confirmed, matcher_ids, path)
    else:
        logger.warning("Unknown award tier: %s", award.tier)
        return EvalResult()


def _maybe_grant(user_id: int, award: AwardDefinition, result: EvalResult):
    """Create an AwardGrant if the user doesn't already have one (active)."""
    existing = AwardGrant.objects.filter(
        user_id=user_id, award=award, revoked_at__isnull=True
    ).exists()

    if existing:
        return

    AwardGrant.objects.create(
        user_id=user_id,
        award=award,
        evidence_at=result.evidence_at,
    )
    logger.info("Granted %s to user %d", award.slug, user_id)


def process_pending_batch(callsign_ids: list[int]):
    """Process a batch of callsign IDs from the awards queue."""
    user_map = resolve_users_for_callsign_ids(callsign_ids)

    for user_id in user_map:
        try:
            evaluate_user(user_id)
        except Exception:
            logger.exception("Error evaluating awards for user %d", user_id)
