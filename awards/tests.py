import pytest

from app.models import AuthUser, CallsignAssociation
from contacts.models import Callsign, Contact, Match

from .evaluate import evaluate_query_award, get_confirmed_contacts
from .models import AwardDefinition, AwardGrant, AwardProgress
from .worker import evaluate_user


def _make_user(username="test@example.com"):
    user = AuthUser.objects.create_user(username=username, email=username, password="test")
    return user


def _make_callsign(call):
    return Callsign.objects.create(callsign=call)


def _make_contact(from_cs, to_cs, **kwargs):
    defaults = {
        "date": 100,
        "time": 720,
        "time_off": 0,
        "band": 8,
        "mode": 29,
        "sub_mode": 0,
        "grid": 0,
        "grid_size": 0,
        "dxcc": 291,
        "zone_cq": 5,
        "zone_itu": 8,
        "tx_power": 0,
    }
    defaults.update(kwargs)
    return Contact.objects.create(from_id=from_cs.id, to_id=to_cs.id, **defaults)


def _make_match(c1, c2):
    import time

    a_id, b_id = sorted([c1.id, c2.id])
    return Match.objects.create(
        matched_at=int(time.time()),
        a_id=a_id,
        b_id=b_id,
        a_call_id=c1.from_id,
        b_call_id=c2.from_id,
    )


@pytest.mark.django_db
def test_count_evaluator_basic():
    rule = {"type": "count", "threshold": 2}
    # No contacts → not earned
    result = evaluate_query_award([], rule)
    assert not result.earned
    assert result.progress["count"] == 0
    assert result.progress["needed"] == 2


@pytest.mark.django_db
def test_count_evaluator_with_contacts():
    cs_me = _make_callsign("TCOUNT")
    cs_other = _make_callsign("TCOUNT2")
    c1 = _make_contact(cs_me, cs_other, date=100, time=100)
    c2 = _make_contact(cs_me, cs_other, date=101, time=100)
    c3 = _make_contact(cs_me, cs_other, date=102, time=100)

    rule = {"type": "count", "threshold": 2}
    result = evaluate_query_award([c1, c2, c3], rule)
    assert result.earned
    assert result.progress["count"] == 3


@pytest.mark.django_db
def test_count_distinct_dxcc():
    cs_me = _make_callsign("TCD1")
    cs_a = _make_callsign("TCD2")
    cs_b = _make_callsign("TCD3")
    c1 = _make_contact(cs_me, cs_a, dxcc=291)
    c2 = _make_contact(cs_me, cs_b, dxcc=230, date=101)
    c3 = _make_contact(cs_me, cs_a, dxcc=291, date=102)  # duplicate DXCC

    rule = {"type": "count_distinct", "field": "dxcc", "thresholds": [3]}
    result = evaluate_query_award([c1, c2, c3], rule)
    assert not result.earned
    assert result.progress["count"] == 2

    rule2 = {"type": "count_distinct", "field": "dxcc", "thresholds": [2]}
    result2 = evaluate_query_award([c1, c2, c3], rule2)
    assert result2.earned


@pytest.mark.django_db
def test_count_distinct_with_band_filter():
    cs_me = _make_callsign("TCDF1")
    cs_other = _make_callsign("TCDF2")
    c1 = _make_contact(cs_me, cs_other, dxcc=291, band=8)
    c2 = _make_contact(cs_me, cs_other, dxcc=230, band=6, date=101)
    c3 = _make_contact(cs_me, cs_other, dxcc=339, band=8, date=102)

    rule = {"type": "count_distinct", "field": "dxcc", "filter": {"band": 8}, "thresholds": [2]}
    result = evaluate_query_award([c1, c2, c3], rule)
    assert result.earned
    assert result.progress["count"] == 2  # only band=8 contacts


@pytest.mark.django_db
def test_collect_all():
    cs_me = _make_callsign("TCA1")
    cs_other = _make_callsign("TCA2")
    c1 = _make_contact(cs_me, cs_other, zone_cq=5)
    c2 = _make_contact(cs_me, cs_other, zone_cq=14, date=101)

    rule = {"type": "collect_all", "field": "zone_cq", "required": [5, 14, 25]}
    result = evaluate_query_award([c1, c2], rule)
    assert not result.earned
    assert set(result.progress["worked"]) == {5, 14}
    assert result.progress["missing"] == [25]


@pytest.mark.django_db
def test_collect_all_earned():
    cs_me = _make_callsign("TCAE1")
    cs_other = _make_callsign("TCAE2")
    c1 = _make_contact(cs_me, cs_other, zone_cq=5)
    c2 = _make_contact(cs_me, cs_other, zone_cq=14, date=101)
    c3 = _make_contact(cs_me, cs_other, zone_cq=25, date=102)

    rule = {"type": "collect_all", "field": "zone_cq", "required": [5, 14, 25]}
    result = evaluate_query_award([c1, c2, c3], rule)
    assert result.earned
    assert result.progress["missing"] == []


@pytest.mark.django_db
def test_get_confirmed_contacts():
    cs_me = _make_callsign("TGCC1")
    cs_other = _make_callsign("TGCC2")
    c1 = _make_contact(cs_me, cs_other, date=100)
    c2 = _make_contact(cs_other, cs_me, date=100, time=725)
    _make_contact(cs_me, cs_other, date=101)  # unmatched

    _make_match(c1, c2)

    confirmed = get_confirmed_contacts([cs_me.id])
    assert len(confirmed) == 1
    assert confirmed[0].id == c1.id


@pytest.mark.django_db
def test_evaluate_user_grants_awards():
    user = _make_user("awards-test@example.com")
    cs_me = _make_callsign("TEU1")
    cs_other = _make_callsign("TEU2")
    CallsignAssociation.objects.create(callsign="TEU1", user=user)

    # Create 3 confirmed contacts
    for i in range(3):
        c_mine = _make_contact(cs_me, cs_other, date=100 + i)
        c_theirs = _make_contact(cs_other, cs_me, date=100 + i, time=725)
        _make_match(c_mine, c_theirs)

    AwardDefinition.objects.create(
        slug="test-first",
        name="Test First",
        category="test",
        tier=AwardDefinition.Tier.QUERY,
        evaluator={"type": "count", "threshold": 1},
    )
    AwardDefinition.objects.create(
        slug="test-five",
        name="Test Five",
        category="test",
        tier=AwardDefinition.Tier.QUERY,
        evaluator={"type": "count", "threshold": 5},
    )

    evaluate_user(user.id)

    # Should have earned "first" but not "five"
    grants = list(AwardGrant.objects.filter(user=user).values_list("award__slug", flat=True))
    assert "test-first" in grants
    assert "test-five" not in grants

    # Both should have progress
    progress_slugs = list(
        AwardProgress.objects.filter(user=user).values_list("award__slug", flat=True)
    )
    assert "test-first" in progress_slugs
    assert "test-five" in progress_slugs

    five_progress = AwardProgress.objects.get(user=user, award__slug="test-five")
    assert five_progress.detail["count"] == 3
    assert five_progress.detail["needed"] == 5


@pytest.mark.django_db
def test_evaluate_user_idempotent():
    """Running evaluate_user twice shouldn't create duplicate grants."""
    user = _make_user("awards-idem@example.com")
    cs_me = _make_callsign("TIDEM1")
    cs_other = _make_callsign("TIDEM2")
    CallsignAssociation.objects.create(callsign="TIDEM1", user=user)

    c_mine = _make_contact(cs_me, cs_other, date=100)
    c_theirs = _make_contact(cs_other, cs_me, date=100, time=725)
    _make_match(c_mine, c_theirs)

    AwardDefinition.objects.create(
        slug="test-idem",
        name="Test Idempotent",
        category="test",
        tier=AwardDefinition.Tier.QUERY,
        evaluator={"type": "count", "threshold": 1},
    )

    evaluate_user(user.id)
    evaluate_user(user.id)

    assert AwardGrant.objects.filter(user=user, award__slug="test-idem").count() == 1
