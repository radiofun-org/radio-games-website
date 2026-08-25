import gzip

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from app.models import AuthUser, CallsignAssociation, LogUpload
from contacts.models import Callsign, Contact, Match


@pytest.fixture()
def user(db):
    return AuthUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture()
def api_client(user):
    return Client(), user.api_key


def test_callsign_lookup(db):
    user = AuthUser.objects.create_user(username="lookup", password="testpass123")
    CallsignAssociation.objects.create(
        callsign="W1AW",
        user=user,
        name="ARRL",
        country="United States",
        grid_square="FN31pr",
        latitude=41.71,
        longitude=-72.73,
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
    data = resp.json()
    assert data["results"] == []
    assert data["next"] is None
    assert data["previous"] is None


def test_matches_returns_data(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user, name="ARRL")
    other = AuthUser.objects.create_user(username="other", password="testpass123")
    CallsignAssociation.objects.create(callsign="VE3ABC", user=other, name="John")

    # Create matcher-side callsign records (normally written by the Go matcher)
    mc_a = Callsign.objects.create(callsign="W1AW")
    mc_b = Callsign.objects.create(callsign="VE3ABC")

    Match.objects.create(
        matched_at=1700000000, a_id=1, b_id=2, a_call_id=mc_a.id, b_call_id=mc_b.id
    )

    resp = client.get("/api/matches/", HTTP_X_API_KEY=api_key)
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["a_callsign"] == "W1AW"
    assert results[0]["b_callsign"] == "VE3ABC"
    assert results[0]["matched_at"] == 1700000000


def test_matches_cursor_pagination(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)
    mc_a = Callsign.objects.create(callsign="W1AW")
    mc_b = Callsign.objects.create(callsign="VE3ABC")

    for i in range(3):
        Match.objects.create(
            matched_at=1700000000 + i, a_id=i, b_id=i + 10, a_call_id=mc_a.id, b_call_id=mc_b.id
        )

    resp = client.get("/api/matches/?page_size=2", HTTP_X_API_KEY=api_key)
    assert resp.status_code == 200
    page = resp.json()
    assert [m["matched_at"] for m in page["results"]] == [1700000002, 1700000001]
    assert page["next"] is not None

    resp = client.get(page["next"], HTTP_X_API_KEY=api_key)
    assert resp.status_code == 200
    page = resp.json()
    assert [m["matched_at"] for m in page["results"]] == [1700000000]
    assert page["next"] is None


def test_upload_requires_auth(db):
    resp = Client().post("/api/upload/")
    assert resp.status_code == 401


def test_upload_invalid_callsign(api_client):
    client, api_key = api_client
    adif = SimpleUploadedFile("test.adi", b"fake adif content")
    resp = client.post("/api/upload/?callsign=NOCALL", {"log_file": adif}, HTTP_X_API_KEY=api_key)
    assert resp.status_code == 400


def test_upload_success(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)

    adif = SimpleUploadedFile("test.adi", b"fake adif content")
    resp = client.post("/api/upload/?callsign=W1AW", {"log_file": adif}, HTTP_X_API_KEY=api_key)
    assert resp.status_code == 201
    data = resp.json()
    assert data["callsign"] == "W1AW"
    assert LogUpload.objects.filter(id=data["id"], callsign="W1AW", user=user).exists()


def test_upload_rejects_oversized_file(api_client, settings):
    settings.MAX_LOG_FILE_SIZE = 100
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)

    adif = SimpleUploadedFile("big.adi", b"x" * 101)
    resp = client.post("/api/upload/?callsign=W1AW", {"log_file": adif}, HTTP_X_API_KEY=api_key)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"]


def test_upload_rejects_bad_extension(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)

    txt = SimpleUploadedFile("notes.txt", b"not adif")
    resp = client.post("/api/upload/?callsign=W1AW", {"log_file": txt}, HTTP_X_API_KEY=api_key)
    assert resp.status_code == 400


def test_matches_adif_export(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)

    me = Callsign.objects.create(callsign="W1AW")
    them = Callsign.objects.create(callsign="K3LR")

    my_contact = Contact.objects.create(
        date=27000,
        time=600,
        time_off=0,
        from_id=me.id,
        to_id=them.id,
        band=8,
        mode=29,
        sub_mode=0,
        grid=0,
        grid_size=0,
        dxcc=291,
        zone_cq=0,
        zone_itu=0,
        tx_power=0,
    )
    their_contact = Contact.objects.create(
        date=27000,
        time=601,
        time_off=0,
        from_id=them.id,
        to_id=me.id,
        band=8,
        mode=29,
        sub_mode=0,
        grid=0,
        grid_size=0,
        dxcc=291,
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

    resp = client.get("/api/matches/adif", HTTP_X_API_KEY=api_key)
    assert resp.status_code == 200
    body = gzip.decompress(b"".join(resp.streaming_content if resp.streaming else [resp.content]))
    text = body.decode()
    assert "<EOH>" in text
    assert "<CALL:4>K3LR" in text
    assert "<STATION_CALLSIGN:4>W1AW" in text
    assert "<EOR>" in text

    # since filter excludes older matches
    resp = client.get("/api/matches/adif?since=1700000001", HTTP_X_API_KEY=api_key)
    body = gzip.decompress(b"".join(resp.streaming_content if resp.streaming else [resp.content]))
    assert "<EOR>" not in body.decode()


def test_upload_replaces(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)
    original = LogUpload.objects.create(
        log_file=SimpleUploadedFile("orig.adi", b"<EOH>\n"), callsign="W1AW", user=user
    )

    adif = SimpleUploadedFile("fixed.adi", b"<EOH>\n")
    resp = client.post(
        f"/api/upload/?callsign=W1AW&replaces={original.pk}",
        {"log_file": adif},
        HTTP_X_API_KEY=api_key,
    )
    assert resp.status_code == 201
    new = LogUpload.objects.get(pk=resp.json()["id"])
    assert new.replaces == original


def test_upload_replaces_rejects_other_users_upload(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)
    other = AuthUser.objects.create_user(username="other2", password="testpass123")
    theirs = LogUpload.objects.create(
        log_file=SimpleUploadedFile("theirs.adi", b"<EOH>\n"), callsign="VE3XYZ", user=other
    )

    adif = SimpleUploadedFile("fixed.adi", b"<EOH>\n")
    resp = client.post(
        f"/api/upload/?callsign=W1AW&replaces={theirs.pk}",
        {"log_file": adif},
        HTTP_X_API_KEY=api_key,
    )
    assert resp.status_code == 400


def test_upload_replaces_rejects_callsign_mismatch(api_client):
    client, api_key = api_client
    user = AuthUser.objects.get(username="testuser")
    CallsignAssociation.objects.create(callsign="W1AW", user=user)
    CallsignAssociation.objects.create(callsign="W1AW/P", user=user)
    original = LogUpload.objects.create(
        log_file=SimpleUploadedFile("orig.adi", b"<EOH>\n"), callsign="W1AW/P", user=user
    )

    adif = SimpleUploadedFile("fixed.adi", b"<EOH>\n")
    resp = client.post(
        f"/api/upload/?callsign=W1AW&replaces={original.pk}",
        {"log_file": adif},
        HTTP_X_API_KEY=api_key,
    )
    assert resp.status_code == 400
