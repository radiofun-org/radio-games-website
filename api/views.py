from datetime import datetime

import redis
from django.conf import settings
from django.db.models import Q
from ninja import File, NinjaAPI, Schema
from ninja.files import UploadedFile
from ninja.security import APIKeyHeader

from app.models import AuthUser, CallsignAssociation, LogUpload
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
    assoc = CallsignAssociation.objects.select_related("user").filter(callsign=call.upper()).first()
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
def log_upload(request, callsign: str, log_file: UploadedFile = File(...)):
    """Upload an ADIF log file for matching. The callsign must already be
    in your profile. The file is queued for processing by the matcher."""
    user = request.auth
    cs = CallsignAssociation.objects.filter(user=user, callsign=callsign.upper()).first()
    if not cs:
        return api.create_response(request, {"detail": "Callsign not in your profile"}, status=400)
    upload = LogUpload.objects.create(log_file=log_file, callsign=cs.callsign, user=user)
    r = redis.from_url(settings.REDIS_URL)
    r.lpush("log_upload_queue", upload.id)
    return 201, UploadOut(id=upload.id, callsign=cs.callsign)


@api.get("/matches/", response=list[MatchOut], auth=ApiKeyAuth())
def match_list(request, limit: int = 50, offset: int = 0):
    """List confirmed matches for your callsigns, newest first.
    A match means both parties uploaded logs containing the same QSO."""
    user = request.auth
    user_callsigns = list(
        CallsignAssociation.objects.filter(user=user).values_list("callsign", flat=True)
    )
    if not user_callsigns:
        return []
    matcher_ids = list(
        Callsign.objects.filter(callsign__in=user_callsigns).values_list("id", flat=True)
    )
    if not matcher_ids:
        return []
    matches = list(
        Match.objects.filter(
            Q(a_call_id__in=matcher_ids) | Q(b_call_id__in=matcher_ids)
        ).order_by("-matched_at")[offset : offset + limit]
    )
    all_ids = {m.a_call_id for m in matches} | {m.b_call_id for m in matches}
    cs_map = dict(Callsign.objects.filter(id__in=all_ids).values_list("id", "callsign"))
    return [
        MatchOut(
            id=m.id,
            matched_at=m.matched_at,
            a_callsign=cs_map.get(m.a_call_id, "?"),
            b_callsign=cs_map.get(m.b_call_id, "?"),
        )
        for m in matches
    ]
