from unittest.mock import AsyncMock, patch

import pytest
from django.test import Client

from app.models import AuthUser, CallsignAssociation

CALLOOK_RESULT = {
    "name": "ARRL HQ OPERATORS CLUB",
    "country": "United States",
    "grid_square": "FN31pr",
    "latitude": 41.714707,
    "longitude": -72.728411,
    "effective_date": "2020-12-08",
}


@pytest.fixture()
def user(db):
    return AuthUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture()
def other_user(db):
    return AuthUser.objects.create_user(username="other", password="testpass123")


@pytest.fixture()
def logged_in(user):
    client = Client()
    client.login(username="testuser", password="testpass123")
    return client


def test_profile_shows_callsigns(logged_in, user):
    CallsignAssociation.objects.create(callsign="W1AW", user=user, name="ARRL")
    resp = logged_in.get("/profile/")
    assert resp.status_code == 200
    assert b"W1AW" in resp.content
    assert b"ARRL" in resp.content


def test_add_callsign(logged_in, user):
    resp = logged_in.post(
        "/profile/callsign/add/",
        {
            "callsign": "W1AW",
            "name": "ARRL HQ",
            "country": "United States",
            "grid_square": "FN31pr",
        },
    )
    assert resp.status_code == 302
    cs = CallsignAssociation.objects.get(user=user, callsign="W1AW")
    assert cs.name == "ARRL HQ"
    assert cs.country == "United States"
    assert cs.grid_square == "FN31pr"


def test_add_callsign_with_dates(logged_in, user):
    resp = logged_in.post(
        "/profile/callsign/add/",
        {
            "callsign": "W1AW",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
    )
    assert resp.status_code == 302
    cs = CallsignAssociation.objects.get(user=user, callsign="W1AW")
    assert str(cs.start_date) == "2024-01-01"
    assert str(cs.end_date) == "2024-12-31"


def test_add_duplicate_callsign(logged_in, user):
    CallsignAssociation.objects.create(callsign="W1AW", user=user)
    resp = logged_in.post("/profile/callsign/add/", {"callsign": "W1AW"})
    assert resp.status_code == 302
    assert CallsignAssociation.objects.filter(user=user, callsign="W1AW").count() == 1


def test_delete_own_callsign(logged_in, user):
    cs = CallsignAssociation.objects.create(callsign="W1AW", user=user)
    resp = logged_in.post(f"/profile/callsign/{cs.pk}/delete/")
    assert resp.status_code == 302
    assert not CallsignAssociation.objects.filter(pk=cs.pk).exists()


def test_cannot_delete_other_users_callsign(logged_in, other_user):
    cs = CallsignAssociation.objects.create(callsign="W1AW", user=other_user)
    resp = logged_in.post(f"/profile/callsign/{cs.pk}/delete/")
    assert resp.status_code == 302
    assert CallsignAssociation.objects.filter(pk=cs.pk).exists()


def test_add_callsign_get_not_allowed(logged_in):
    resp = logged_in.get("/profile/callsign/add/")
    assert resp.status_code == 405


def test_callsign_uppercased(logged_in, user):
    logged_in.post("/profile/callsign/add/", {"callsign": "w1aw"})
    assert CallsignAssociation.objects.filter(user=user, callsign="W1AW").exists()


@patch("app.views.fetch_callook", new_callable=AsyncMock)
def test_callsign_lookup(mock_callook, logged_in):
    mock_callook.return_value = CALLOOK_RESULT
    resp = logged_in.get("/profile/callsign/lookup/?callsign=W1AW")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ARRL HQ OPERATORS CLUB"
    assert data["country"] == "United States"
    assert data["grid_square"] == "FN31pr"
    assert data["effective_date"] == "2020-12-08"


@patch("app.views.fetch_callook", new_callable=AsyncMock)
def test_callsign_lookup_not_found(mock_callook, logged_in):
    mock_callook.return_value = None
    resp = logged_in.get("/profile/callsign/lookup/?callsign=INVALID")
    assert resp.status_code == 404


def test_edit_callsign(logged_in, user):
    cs = CallsignAssociation.objects.create(callsign="W1AW", user=user, name="Old")
    resp = logged_in.post(
        f"/profile/callsign/{cs.pk}/edit/",
        {
            "name": "New Name",
            "country": "United States",
            "grid_square": "FN31",
            "start_date": "2024-01-01",
            "end_date": "",
        },
    )
    assert resp.status_code == 302
    cs.refresh_from_db()
    assert cs.name == "New Name"
    assert cs.grid_square == "FN31"
    assert str(cs.start_date) == "2024-01-01"
    assert cs.end_date is None


def test_cannot_edit_other_users_callsign(logged_in, other_user):
    cs = CallsignAssociation.objects.create(callsign="W1AW", user=other_user, name="Old")
    resp = logged_in.post(f"/profile/callsign/{cs.pk}/edit/", {"name": "Hacked"})
    assert resp.status_code == 302
    cs.refresh_from_db()
    assert cs.name == "Old"


def test_logbook_empty(logged_in):
    resp = logged_in.get("/logbook/")
    assert resp.status_code == 200
    assert b"No contacts yet" in resp.content


def test_logbook_shows_contacts(logged_in, user):
    from contacts.models import Callsign, Contact

    CallsignAssociation.objects.create(callsign="N7YHF", user=user)
    me = Callsign.objects.create(callsign="N7YHF")
    them = Callsign.objects.create(callsign="W1AW")

    Contact.objects.create(
        date=27427,  # 2025-02-01 (days since 1950-01-01)
        time=840,  # 14:00 UTC
        time_off=0,
        from_id=me.id,
        to_id=them.id,
        band=8,
        mode=29,
        sub_mode=0,  # 20m FT8
        grid=0,
        grid_size=0,
        dxcc=0,
        zone_cq=0,
        zone_itu=0,
        tx_power=0,
    )

    resp = logged_in.get("/logbook/")
    assert resp.status_code == 200
    assert b"W1AW" in resp.content
    assert b"20m" in resp.content
    assert b"FT8" in resp.content
    assert b"14:00" in resp.content
    assert b"table-success" not in resp.content


def test_logbook_shows_confirmed(logged_in, user):
    from contacts.models import Callsign, Contact, Match

    CallsignAssociation.objects.create(callsign="N7YHF", user=user)
    me = Callsign.objects.create(callsign="N7YHF")
    them = Callsign.objects.create(callsign="W1AW")

    my_contact = Contact.objects.create(
        date=27427,
        time=840,
        time_off=0,
        from_id=me.id,
        to_id=them.id,
        band=8,
        mode=29,
        sub_mode=0,
        grid=0,
        grid_size=0,
        dxcc=0,
        zone_cq=0,
        zone_itu=0,
        tx_power=0,
    )
    their_contact = Contact.objects.create(
        date=27427,
        time=841,
        time_off=0,
        from_id=them.id,
        to_id=me.id,
        band=8,
        mode=29,
        sub_mode=0,
        grid=0,
        grid_size=0,
        dxcc=0,
        zone_cq=0,
        zone_itu=0,
        tx_power=0,
    )
    Match.objects.create(
        matched_at=1700000000,
        a_id=my_contact.id,
        b_id=their_contact.id,
        a_call_id=me.id,
        b_call_id=them.id,
    )

    resp = logged_in.get("/logbook/")
    assert resp.status_code == 200
    assert b"table-success" in resp.content
    assert b"ago" in resp.content  # naturaltime output


def test_login_email_case_insensitive(db):
    AuthUser.objects.create_user(
        username="op@example.com", email="op@example.com", password="testpass123"
    )
    client = Client()
    resp = client.post(
        "/accounts/login/",
        {"username": "Op@Example.COM", "password": "testpass123"},
    )
    assert resp.status_code == 302
