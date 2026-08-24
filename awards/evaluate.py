"""Award evaluation engine.

Evaluates all enabled awards for a given user and their matcher callsign IDs.
Returns which awards are newly earned and progress snapshots for all awards.
"""

import importlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC

from django.db.models import Q

from contacts.models import Contact, Match

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Result of evaluating a single award for a user."""

    earned: bool = False
    # The date of the qualifying contact (for evidence_at).
    evidence_at: datetime | None = None
    # Progress detail for AwardProgress.detail.
    progress: dict = field(default_factory=dict)


def get_confirmed_contacts(matcher_ids: list[int]) -> list[Contact]:
    """Return contacts made by matcher_ids that have a corresponding match."""
    if not matcher_ids:
        return []

    # Get all match rows involving these callsign IDs
    match_rows = Match.objects.filter(
        Q(a_call_id__in=matcher_ids) | Q(b_call_id__in=matcher_ids)
    ).values_list("a_id", "b_id", "a_call_id", "b_call_id")

    my_contact_ids: set[int] = set()
    for a_id, b_id, a_call_id, b_call_id in match_rows:
        if a_call_id in matcher_ids:
            my_contact_ids.add(a_id)
        if b_call_id in matcher_ids:
            my_contact_ids.add(b_id)

    return (
        list(Contact.objects.filter(id__in=my_contact_ids).order_by("date", "time"))
        if my_contact_ids
        else []
    )


# ---------------------------------------------------------------------------
# Query-based evaluator (tier 1 & 2)
# ---------------------------------------------------------------------------


def _eval_count_distinct(contacts: list[Contact], rule: dict) -> EvalResult:
    """Count distinct values of a field across confirmed contacts.

    Rule shape:
        {
            "type": "count_distinct",
            "field": "dxcc",           # Contact field to count
            "filter": {"band": 8},     # Optional filters on Contact fields
            "thresholds": [100, 200]   # Award granted at highest met threshold
        }
    """
    contact_filter = rule.get("filter", {})
    target_field = rule["field"]
    thresholds = sorted(rule.get("thresholds", [1]))

    if not thresholds:
        return EvalResult()

    values: set = set()

    for c in contacts:
        # Apply filters
        if not _contact_matches_filter(c, contact_filter):
            continue
        val = getattr(c, target_field, None)
        if val and val != 0:
            values.add(val)

    count = len(values)
    highest_met = 0
    for t in thresholds:
        if count >= t:
            highest_met = t

    needed = thresholds[-1]
    earned = highest_met >= needed

    # Find evidence_at: the contact that pushed us over the threshold
    evidence_at = None
    if earned:
        evidence_at = _find_evidence_date(contacts, contact_filter, target_field, needed)

    return EvalResult(
        earned=earned,
        evidence_at=evidence_at,
        progress={"count": count, "needed": needed, "threshold_met": highest_met},
    )


def _eval_collect_all(contacts: list[Contact], rule: dict) -> EvalResult:
    """Check if all required values of a field have been worked.

    Rule shape:
        {
            "type": "collect_all",
            "field": "zone_cq",
            "required": [1, 2, 3, ..., 40],
            "filter": {}
        }
    """
    contact_filter = rule.get("filter", {})
    target_field = rule["field"]
    required = set(rule["required"])

    worked: set = set()
    for c in contacts:
        if not _contact_matches_filter(c, contact_filter):
            continue
        val = getattr(c, target_field, None)
        if val in required:
            worked.add(val)

    missing = required - worked
    earned = len(missing) == 0

    evidence_at = None
    if earned:
        evidence_at = _find_collect_all_evidence(contacts, contact_filter, target_field, required)

    return EvalResult(
        earned=earned,
        evidence_at=evidence_at,
        progress={
            "worked": sorted(worked),
            "needed": sorted(required),
            "missing": sorted(missing),
        },
    )


def _eval_count(contacts: list[Contact], rule: dict) -> EvalResult:
    """Count total confirmed contacts matching filters.

    Rule shape:
        {
            "type": "count",
            "filter": {"band": 8},
            "threshold": 1000
        }
    """
    contact_filter = rule.get("filter", {})
    threshold = rule.get("threshold", 1)

    count = 0
    for c in contacts:
        if _contact_matches_filter(c, contact_filter):
            count += 1

    earned = count >= threshold
    evidence_at = None
    if earned:
        # Walk contacts in order to find the threshold-th one
        seen = 0
        for c in contacts:
            if _contact_matches_filter(c, contact_filter):
                seen += 1
                if seen == threshold:
                    evidence_at = _contact_datetime(c)
                    break

    return EvalResult(
        earned=earned,
        evidence_at=evidence_at,
        progress={"count": count, "needed": threshold},
    )


QUERY_EVALUATORS = {
    "count_distinct": _eval_count_distinct,
    "collect_all": _eval_collect_all,
    "count": _eval_count,
}


def evaluate_query_award(contacts: list[Contact], rule: dict) -> EvalResult:
    """Dispatch to the right query-based evaluator."""
    eval_type = rule.get("type", "")
    evaluator = QUERY_EVALUATORS.get(eval_type)
    if not evaluator:
        logger.warning("Unknown query evaluator type: %s", eval_type)
        return EvalResult()
    return evaluator(contacts, rule)


# ---------------------------------------------------------------------------
# Code-based evaluator (tier 3)
# ---------------------------------------------------------------------------


def evaluate_code_award(
    contacts: list[Contact], matcher_ids: list[int], evaluator_path: str
) -> EvalResult:
    """Import and call a Python evaluator function by dotted path.

    The function must have signature:
        def evaluate(contacts: list[Contact], matcher_ids: list[int]) -> EvalResult
    """
    try:
        module_path, func_name = evaluator_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except ImportError, AttributeError, ValueError:
        logger.exception("Failed to load code evaluator: %s", evaluator_path)
        return EvalResult()

    return func(contacts, matcher_ids)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contact_matches_filter(contact: Contact, filters: dict) -> bool:
    """Check if a contact matches all filter criteria."""
    for field_name, value in filters.items():
        if isinstance(value, list):
            if getattr(contact, field_name, None) not in value:
                return False
        else:
            if getattr(contact, field_name, None) != value:
                return False
    return True


def _contact_datetime(contact: Contact) -> datetime:
    """Convert a Contact's encoded date+time to a datetime."""
    from contacts.decode import EPOCH

    d = EPOCH + timedelta(days=contact.date)
    hours, minutes = divmod(contact.time, 60)
    return datetime(d.year, d.month, d.day, hours, minutes, tzinfo=UTC)


def _find_evidence_date(
    contacts: list[Contact], filters: dict, field: str, threshold: int
) -> datetime | None:
    """Walk contacts in date order to find when the threshold was first met."""
    values: set = set()
    for c in contacts:
        if not _contact_matches_filter(c, filters):
            continue
        val = getattr(c, field, None)
        if val and val != 0:
            values.add(val)
            if len(values) >= threshold:
                return _contact_datetime(c)
    return None


def _find_collect_all_evidence(
    contacts: list[Contact], filters: dict, field: str, required: set
) -> datetime | None:
    """Walk contacts in date order to find when all required values were collected."""
    worked: set = set()
    for c in contacts:
        if not _contact_matches_filter(c, filters):
            continue
        val = getattr(c, field, None)
        if val in required:
            worked.add(val)
            if worked >= required:
                return _contact_datetime(c)
    return None
