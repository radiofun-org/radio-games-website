import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from app.models import AuthUser, CallsignAssociation, LogUpload


@pytest.fixture()
def user(db):
    return AuthUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture()
def api_client(user):
    return Client(), user.api_key


def test_callsign_lookup(db):
    user = AuthUser.objects.create_user(username="lookup", password="testpass123")
    CallsignAssociation.objects.create(
        callsign="W1AW", user=user, name="ARRL", country="United States",
        grid_square="FN31pr", latitude=41.71, longitude=-72.73,
    )
    client = Client()
    resp = client.get("/api/callsign/W1AW/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["callsign"] == "W1AW"
    assert data["name"] == "ARRL"
    assert data["country"] == "United States"
    assert data["grid_square"] == "FN31pr"
    assert data["signed_up"] is not None
    assert data["contact_count"] == 0
    assert data["match_count"] == 0


def test_callsign_lookup_not_found(db):
    resp = Client().get("/api/callsign/ZZZZZ/")
    assert resp.status_code == 404


def test_matches_requires_auth(db):
    resp = Client().get("/api/matches/")
    assert resp.status_code == 401


def test_matches_invalid_key(db):
    resp = Client().get("/api/matches/", HTTP_X_API_KEY="boguskey")
    assert resp.status_code == 401


def test_matches_empty(api_client):
    client, api_key = api_client
    resp = client.get("/api/matches/", HTTP_X_API_KEY=api_key)
    assert resp.status_code == 200
    assert resp.json() == []


def test_matches_returns_data(api_client):
    from contacts.models import Match

    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    cs_a = CallsignAssociation.objects.create(callsign="W1AW", user=user, name="ARRL")
    other = AuthUser.objects.create_user(username="other", password="testpass123")
    cs_b = CallsignAssociation.objects.create(callsign="VE3ABC", user=other, name="John")

    Match.objects.create(matched_at=1700000000, a_id=1, b_id=2, a_call_id=cs_a.id, b_call_id=cs_b.id)

    resp = client.get("/api/matches/", HTTP_X_API_KEY=api_key)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["a_callsign"] == "W1AW"
    assert data[0]["b_callsign"] == "VE3ABC"
    assert data[0]["matched_at"] == 1700000000


def test_upload_requires_auth(db):
    resp = Client().post("/api/upload/")
    assert resp.status_code == 401


def test_upload_invalid_callsign(api_client):
    client, api_key = api_client
    adif = SimpleUploadedFile("test.adi", b"fake adif content")
    resp = client.post(
        "/api/upload/?callsign=NOCALL", {"log_file": adif}, HTTP_X_API_KEY=api_key
    )
    assert resp.status_code == 400


def test_upload_success(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)

    adif = SimpleUploadedFile("test.adi", b"fake adif content")
    resp = client.post(
        "/api/upload/?callsign=W1AW", {"log_file": adif}, HTTP_X_API_KEY=api_key
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["callsign"] == "W1AW"
    assert LogUpload.objects.filter(id=data["id"], callsign="W1AW", user=user).exists()
