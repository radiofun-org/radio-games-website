from unittest.mock import patch

import pytest
from django.test import Client

from app.models import AuthUser, CallsignAssociation

CALLOOK_RESULT = {
    "name": "ARRL HQ OPERATORS CLUB",
    "country": "United States",
    "grid_square": "FN31pr",
    "latitude": 41.714707,
    "longitude": -72.728411,
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


@patch("app.views.fetch_callook")
def test_add_callsign_with_callook(mock_callook, logged_in, user):
    mock_callook.return_value = CALLOOK_RESULT
    resp = logged_in.post("/profile/callsign/add/", {"callsign": "W1AW"})
    assert resp.status_code == 302
    cs = CallsignAssociation.objects.get(user=user, callsign="W1AW")
    assert cs.name == "ARRL HQ OPERATORS CLUB"
    assert cs.country == "United States"
    assert cs.grid_square == "FN31pr"
    assert cs.latitude == pytest.approx(41.714707)
    assert cs.longitude == pytest.approx(-72.728411)


@patch("app.views.fetch_callook")
def test_add_callsign_manual_fallback(mock_callook, logged_in, user):
    mock_callook.return_value = None
    resp = logged_in.post("/profile/callsign/add/", {
        "callsign": "VE3ABC",
        "name": "John",
        "country": "Canada",
        "grid_square": "FN03",
    })
    assert resp.status_code == 302
    cs = CallsignAssociation.objects.get(user=user, callsign="VE3ABC")
    assert cs.name == "John"
    assert cs.country == "Canada"
    assert cs.grid_square == "FN03"


@patch("app.views.fetch_callook")
def test_add_duplicate_callsign(mock_callook, logged_in, user):
    mock_callook.return_value = None
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


@patch("app.views.fetch_callook")
def test_callsign_uppercased(mock_callook, logged_in, user):
    mock_callook.return_value = None
    logged_in.post("/profile/callsign/add/", {"callsign": "w1aw"})
    assert CallsignAssociation.objects.filter(user=user, callsign="W1AW").exists()
