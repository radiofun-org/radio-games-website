import gzip
from datetime import datetime

import redis
from django.conf import settings
from django.db.models import OuterRef, Q, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from ninja import File, NinjaAPI, Schema, Status
from ninja.files import UploadedFile
from ninja.pagination import CursorPagination, paginate
from ninja.security import APIKeyHeader

from app.models import AuthUser, CallsignAssociation, LogUpload
from contacts.decode import decode_band, decode_date, decode_grid, decode_mode, decode_time
from contacts.models import Callsign, Contact, Match


class ApiKeyAuth(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        try:
            return AuthUser.objects.get(api_key=key)
        except AuthUser.DoesNotExist:
            return None


api = NinjaAPI(title="RGMS API", version="1.0.0", urls_namespace="api", docs_url=None)


class CallsignOut(Schema):
    callsign: str
    name: str
    country: str
    grid_square: str
    latitude: float | None
    longitude: float | None
    signed_up: datetime
    contact_count: int
    match_count: int


class UploadOut(Schema):
    id: int
    callsign: str


class MatchOut(Schema):
    id: int
    matched_at: int
    a_callsign: str
    b_callsign: str


@api.get("/callsign/{call}/", response=CallsignOut)
def callsign_lookup(request, call: str):
    """Look up a callsign's profile, including signup date and activity counts.
    Returns 404 if the callsign is not registered."""
    assoc = (
        CallsignAssociation.objects.select_related("user").filter(callsign=call.upper()).first()
    )
    if not assoc:
        return api.create_response(request, {"detail": "Not found"}, status=404)
    matcher_cs = Callsign.objects.filter(callsign=assoc.callsign).first()
    matcher_id = matcher_cs.id if matcher_cs else -1
    return CallsignOut(
        callsign=assoc.callsign,
        name=assoc.name,
        country=assoc.country,
        grid_square=assoc.grid_square,
        latitude=assoc.latitude,
        longitude=assoc.longitude,
        signed_up=assoc.user.date_joined,
        contact_count=Contact.objects.filter(Q(from_id=matcher_id) | Q(to_id=matcher_id)).count(),
        match_count=Match.objects.filter(
            Q(a_call_id=matcher_id) | Q(b_call_id=matcher_id)
        ).count(),
    )


@api.post("/upload/", response={201: UploadOut}, auth=ApiKeyAuth())
def log_upload(request, callsign: str, log_file: File[UploadedFile]):
    """Upload an ADIF log file for matching. The callsign must already be
    in your profile. The file is queued for processing by the matcher."""
    user = request.auth
    cs = CallsignAssociation.objects.filter(user=user, callsign=callsign.upper()).first()
    if not cs:
        return api.create_response(request, {"detail": "Callsign not in your profile"}, status=400)
    upload = LogUpload.objects.create(log_file=log_file, callsign=cs.callsign, user=user)
    r = redis.from_url(settings.REDIS_URL)
    r.lpush("log_upload_queue", upload.pk)
    return Status(201, UploadOut(id=upload.pk, callsign=cs.callsign))


@api.get("/matches/", response=list[MatchOut], auth=ApiKeyAuth())
@paginate(CursorPagination, ordering=("-matched_at",), page_size=50, max_page_size=200)
def match_list(request):
    """List confirmed matches for your callsigns, newest first.
    A match means both parties uploaded logs containing the same QSO.
    Cursor-paginated: follow `next`/`previous` URLs, `page_size` up to 200."""
    user = request.auth
    user_callsigns = list(
        CallsignAssociation.objects.filter(user=user).values_list("callsign", flat=True)
    )
    matcher_ids = list(
        Callsign.objects.filter(callsign__in=user_callsigns).values_list("id", flat=True)
    )
    if not matcher_ids:
        return Match.objects.none()

    def callsign_for(field: str):
        return Coalesce(
            Subquery(Callsign.objects.filter(id=OuterRef(field)).values("callsign")[:1]),
            Value("?"),
            output_field=TextField(),
        )

    return Match.objects.filter(
        Q(a_call_id__in=matcher_ids) | Q(b_call_id__in=matcher_ids)
    ).annotate(a_callsign=callsign_for("a_call_id"), b_callsign=callsign_for("b_call_id"))


def _adif_field(tag: str, value: str) -> str:
    return f"<{tag}:{len(value)}>{value}" if value else ""


def _contact_to_adif(contact: Contact, callsign_map: dict[int, str]) -> str:
    """Build one ADIF record from a Contact row."""
    d = decode_date(contact.date)
    fields = [
        _adif_field("CALL", callsign_map.get(contact.to_id, "")),
        _adif_field("STATION_CALLSIGN", callsign_map.get(contact.from_id, "")),
        _adif_field("QSO_DATE", d.strftime("%Y%m%d")),
        _adif_field("TIME_ON", decode_time(contact.time).replace(":", "")),
        _adif_field("BAND", decode_band(contact.band)),
        _adif_field("MODE", decode_mode(contact.mode, contact.sub_mode)),
    ]
    if grid := decode_grid(contact.grid, contact.grid_size):
        fields.append(_adif_field("GRIDSQUARE", grid))
    if contact.dxcc:
        fields.append(_adif_field("DXCC", str(contact.dxcc)))
    fields.append("<EOR>")
    return "".join(f for f in fields if f)


@api.get("/matches/adif", auth=ApiKeyAuth(), include_in_schema=True)
def matches_adif(request, since: int = 0):
    """Export confirmed matches as ADIF. Returns gzipped ADIF data.

    The `since` parameter is a Unix timestamp; only matches confirmed after
    that time are included. This allows incremental syncing — store the latest
    `matched_at` value and pass it next time."""
    user = request.auth
    user_callsigns = list(
        CallsignAssociation.objects.filter(user=user).values_list("callsign", flat=True)
    )
    if not user_callsigns:
        return HttpResponse(
            gzip.compress(b""),
            content_type="application/gzip",
            headers={"Content-Encoding": "gzip"},
        )

    matcher_ids = list(
        Callsign.objects.filter(callsign__in=user_callsigns).values_list("id", flat=True)
    )
    if not matcher_ids:
        return HttpResponse(
            gzip.compress(b""),
            content_type="application/gzip",
            headers={"Content-Encoding": "gzip"},
        )

    matches_qs = Match.objects.filter(Q(a_call_id__in=matcher_ids) | Q(b_call_id__in=matcher_ids))
    if since:
        matches_qs = matches_qs.filter(matched_at__gt=since)
    matches = list(matches_qs.order_by("matched_at"))

    if not matches:
        return HttpResponse(
            gzip.compress(b""),
            content_type="application/gzip",
            headers={"Content-Encoding": "gzip"},
        )

    # Determine which contact ID is "ours" vs the other station
    # For each match: if a_call_id is ours, our contact is a_id; otherwise b_id
    matcher_id_set = set(matcher_ids)
    our_contact_ids = set()
    for m in matches:
        if m.a_call_id in matcher_id_set:
            our_contact_ids.add(m.a_id)
        if m.b_call_id in matcher_id_set:
            our_contact_ids.add(m.b_id)

    contacts_map = {c.id: c for c in Contact.objects.filter(id__in=our_contact_ids)}

    # Resolve callsign IDs
    all_cs_ids = set()
    for c in contacts_map.values():
        all_cs_ids.add(c.from_id)
        all_cs_ids.add(c.to_id)
    callsign_map = dict(Callsign.objects.filter(id__in=all_cs_ids).values_list("id", "callsign"))

    # Build ADIF
    header = "ADIF export from radio.games\n<ADIF_VER:5>3.1.5\n<PROGRAMID:10>radio.games\n<EOH>\n"
    records = []
    for m in matches:
        if m.a_call_id in matcher_id_set and m.a_id in contacts_map:
            records.append(_contact_to_adif(contacts_map[m.a_id], callsign_map))
        if m.b_call_id in matcher_id_set and m.b_id in contacts_map:
            records.append(_contact_to_adif(contacts_map[m.b_id], callsign_map))

    adif_body = header + "\n".join(records) + "\n"
    compressed = gzip.compress(adif_body.encode())

    return HttpResponse(
        compressed,
        content_type="application/gzip",
        headers={
            "Content-Encoding": "gzip",
            "Content-Disposition": "attachment; filename=matches.adi",
        },
    )
