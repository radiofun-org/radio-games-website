from dataclasses import dataclass
from datetime import datetime, UTC

import httpx
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from contacts.decode import (
    BANDS,
    MODES,
    decode_band,
    decode_date,
    decode_dxcc,
    decode_grid,
    decode_mode,
    decode_time,
)
from awards.models import AwardDefinition, AwardGrant, AwardProgress
from contacts.models import Callsign, Contact, Match

from oauth2_provider.models import Application

from .forms import LoginForm, LogUploadForm, SignUpForm
from .models import CallsignAssociation, LogUpload, generate_api_key
from .redis_client import client as redis_client

BACKEND = "django.contrib.auth.backends.ModelBackend"


def _matcher_ids_for(user) -> list[int]:
    """IDs in the matcher's callsign table for every callsign the user has claimed."""
    callsigns = list(
        CallsignAssociation.objects.filter(user=user).values_list("callsign", flat=True)
    )
    if not callsigns:
        return []
    return list(Callsign.objects.filter(callsign__in=callsigns).values_list("id", flat=True))


def _contact_stats(matcher_ids: list[int]) -> dict:
    """Top modes, bands, and countries across contacts the user logged as the 'from' station."""
    stats: dict[str, list] = {"by_mode": [], "by_band": [], "by_country": []}
    if not matcher_ids:
        return stats
    user_contacts = Contact.objects.filter(from_id__in=matcher_ids)

    mode_counts = user_contacts.values("mode").annotate(count=Count("id")).order_by("-count")[:15]
    stats["by_mode"] = [
        {"label": MODES.get(row["mode"], f"?{row['mode']}"), "count": row["count"]}
        for row in mode_counts
    ]

    band_counts = user_contacts.values("band").annotate(count=Count("id")).order_by("-count")[:15]
    stats["by_band"] = [
        {"label": BANDS.get(row["band"], f"?{row['band']}"), "count": row["count"]}
        for row in band_counts
    ]

    dxcc_counts = (
        user_contacts.values("dxcc")
        .annotate(count=Count("id"))
        .filter(dxcc__gt=0)
        .order_by("-count")[:15]
    )
    stats["by_country"] = [
        {"label": decode_dxcc(row["dxcc"]), "count": row["count"]} for row in dxcc_counts
    ]
    return stats


def _award_progress_fraction(detail: dict) -> float | None:
    """Fraction complete from an AwardProgress.detail; None when the shape has no denominator."""
    count, needed = detail.get("count"), detail.get("needed")
    if isinstance(count, int) and isinstance(needed, int) and needed > 0:
        return min(count / needed, 1.0)
    worked = detail.get("worked")
    if isinstance(worked, list) and isinstance(needed, list) and needed:
        return min(len(worked) / len(needed), 1.0)
    return None


@dataclass
class AwardProgressItem:
    award: AwardDefinition
    fraction: float
    percent: int
    label: str


def _award_progress_label(detail: dict) -> str:
    if isinstance(detail.get("needed"), list):
        return f"{len(detail.get('worked', []))} / {len(detail['needed'])}"
    return f"{detail.get('count', 0)} / {detail.get('needed', '?')}"


def dashboard(request):
    user = request.user
    callsign_count = CallsignAssociation.objects.filter(user=user).count()
    matcher_ids = _matcher_ids_for(user)
    contact_count = Contact.objects.filter(from_id__in=matcher_ids).count() if matcher_ids else 0
    match_count = (
        Match.objects.filter(Q(a_call_id__in=matcher_ids) | Q(b_call_id__in=matcher_ids)).count()
        if matcher_ids
        else 0
    )
    uploads = LogUpload.objects.filter(user=user).order_by("-upload_time")
    upload_count = uploads.count()

    grants = list(
        AwardGrant.objects.filter(user=user, revoked_at__isnull=True)
        .select_related("award")
        .order_by("-granted_at")
    )
    earned_award_ids = {g.award.pk for g in grants}

    in_progress: list[AwardProgressItem] = []
    progress_rows = (
        AwardProgress.objects.filter(user=user, award__enabled=True)
        .exclude(award__pk__in=earned_award_ids)
        .select_related("award")
    )
    for row in progress_rows:
        fraction = _award_progress_fraction(row.detail)
        if not fraction:
            continue
        in_progress.append(
            AwardProgressItem(
                award=row.award,
                fraction=fraction,
                percent=round(fraction * 100),
                label=_award_progress_label(row.detail),
            )
        )
    in_progress.sort(key=lambda item: -item.fraction)

    steps = {
        "callsign": callsign_count > 0,
        "upload": upload_count > 0,
        "confirmed": match_count > 0,
    }

    return render(
        request,
        "app/dashboard.html",
        {
            "steps": steps,
            "setup_done": all(steps.values()),
            "contact_count": contact_count,
            "match_count": match_count,
            "upload_count": upload_count,
            "award_count": len(grants),
            "recent_grants": grants[:6],
            "in_progress": in_progress[:6],
            "recent_uploads": uploads[:5],
            "stats": _contact_stats(matcher_ids),
        },
    )


def index(request):
    if request.user.is_authenticated:
        return dashboard(request)

    is_login = "login" in request.GET or request.POST.get("form_type") == "login"
    signup_form = SignUpForm()
    login_form = LoginForm()

    if request.method == "POST":
        if is_login:
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                login(request, login_form.user, backend=BACKEND)
                return redirect("index")
        else:
            signup_form = SignUpForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save()
                login(request, user, backend=BACKEND)
                return redirect("index")

    return render(
        request,
        "app/index.html",
        {
            "signup_form": signup_form,
            "login_form": login_form,
            "is_login": is_login,
        },
    )


def api_docs(request):
    return render(request, "app/api_docs.html")


def how_it_works(request):
    return render(request, "app/how-it-works.html")


def about(request):
    return render(request, "app/about.html")


def privacy(request):
    return render(request, "app/privacy.html")


@login_required()
def upload(request):
    # A re-upload corrects a specific earlier upload; the callsign is locked
    # to the original's so the matcher can diff the two files.
    replaces = None
    replaces_id = request.POST.get("replaces") or request.GET.get("reupload")
    if replaces_id:
        replaces = LogUpload.objects.filter(pk=replaces_id, user=request.user).first()
        if not replaces:
            messages.error(request, "The log to re-upload was not found.")
            return redirect("upload")

    if request.method == "POST":
        data = request.POST
        if replaces:
            data = request.POST.copy()
            data["callsign"] = replaces.callsign
        form = LogUploadForm(data, request.FILES, user=request.user)
        if form.is_valid():
            log_upload = LogUpload(
                log_file=form.cleaned_data["log_file"],
                callsign=form.cleaned_data["callsign"],
                user=request.user,
                replaces=replaces,
            )
            log_upload.save()

            redis_client.lpush("log_upload_queue", log_upload.pk)

            messages.success(request, "Log uploaded successfully! It will be processed shortly.")
            return redirect("upload")
    else:
        initial = {"callsign": replaces.callsign} if replaces else None
        form = LogUploadForm(user=request.user, initial=initial)
    recent_uploads = LogUpload.objects.filter(user=request.user).order_by("-upload_time")[:10]
    has_callsigns = CallsignAssociation.objects.filter(user=request.user).exists()
    return render(
        request,
        "app/upload.html",
        {
            "form": form,
            "recent_uploads": recent_uploads,
            "replaces": replaces,
            "has_callsigns": has_callsigns,
        },
    )


@login_required()
def profile(request):
    callsigns = CallsignAssociation.objects.filter(user=request.user)
    return render(request, "app/profile.html", {"callsigns": callsigns})


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def account_delete(request) -> HttpResponseRedirect:
    """Erase the account and the data it provided (GDPR right to erasure).

    Deletes the user's uploads (rows and files), their matcher contacts, and
    the matches those contacts made, then queues the counterparties for award
    re-evaluation: their confirmations changed, though grants they already
    earned stand. Counterparties' own log entries and the bare callsign rows
    stay — a QSO in someone else's log is that operator's record.
    """
    user = request.user

    user_calls = list(
        CallsignAssociation.objects.filter(user=user).values_list("callsign", flat=True)
    )
    matcher_ids = list(
        Callsign.objects.filter(callsign__in=user_calls).values_list("id", flat=True)
    )

    affected: set[int] = set()
    with transaction.atomic():
        contact_ids = list(
            Contact.objects.filter(from_id__in=matcher_ids).values_list("id", flat=True)
        )
        if contact_ids:
            match_qs = Match.objects.filter(Q(a_id__in=contact_ids) | Q(b_id__in=contact_ids))
            for a_call_id, b_call_id in match_qs.values_list("a_call_id", "b_call_id"):
                affected.add(a_call_id)
                affected.add(b_call_id)
            match_qs.delete()
            Contact.objects.filter(id__in=contact_ids).delete()

        # FileField files aren't removed by row deletion; delete them
        # explicitly before the user cascade removes the rows.
        for log_upload in LogUpload.objects.filter(user=user):
            log_upload.log_file.delete(save=False)

        logout(request)
        user.delete()

    # Only counterparties need re-evaluation; the deleted user's callsigns
    # no longer resolve to anyone.
    affected -= set(matcher_ids)
    if affected:
        redis_client.sadd("awards_eval_pending", *affected)

    return redirect("index")


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def api_key_reset(request) -> HttpResponseRedirect:
    request.user.api_key = generate_api_key()
    request.user.save(update_fields=["api_key"])
    messages.success(request, "API key has been reset.")
    return redirect("profile")


def public_callsign(request, callsign: str):
    callsign = callsign.upper()
    assoc = CallsignAssociation.objects.select_related("user").filter(callsign=callsign).first()
    if not assoc:
        return render(request, "app/public_callsign.html", {"callsign": callsign, "found": False})

    matcher_cs = Callsign.objects.filter(callsign=callsign).first()
    matcher_id = matcher_cs.id if matcher_cs else -1
    contact_count = Contact.objects.filter(Q(from_id=matcher_id) | Q(to_id=matcher_id)).count()
    match_count = Match.objects.filter(Q(a_call_id=matcher_id) | Q(b_call_id=matcher_id)).count()

    return render(
        request,
        "app/public_callsign.html",
        {
            "callsign": callsign,
            "found": True,
            "assoc": assoc,
            "contact_count": contact_count,
            "match_count": match_count,
        },
    )


LOGBOOK_PAGE_SIZE = 100


@login_required()
def logbook(request):
    user = request.user
    user_callsigns = list(
        CallsignAssociation.objects.filter(user=user).values_list("callsign", flat=True)
    )
    if not user_callsigns:
        return render(request, "app/logbook.html", {"rows": [], "page": 1, "has_next": False})

    matcher_ids = list(
        Callsign.objects.filter(callsign__in=user_callsigns).values_list("id", flat=True)
    )
    if not matcher_ids:
        return render(request, "app/logbook.html", {"rows": [], "page": 1, "has_next": False})

    page = max(1, int(request.GET.get("page", 1)))
    offset = (page - 1) * LOGBOOK_PAGE_SIZE

    contacts = list(
        Contact.objects.filter(from_id__in=matcher_ids).order_by("-date", "-time")[
            offset : offset + LOGBOOK_PAGE_SIZE + 1
        ]
    )
    has_next = len(contacts) > LOGBOOK_PAGE_SIZE
    contacts = contacts[:LOGBOOK_PAGE_SIZE]

    # Resolve callsign IDs → strings (both from and to)
    all_cs_ids = {c.to_id for c in contacts} | {c.from_id for c in contacts}
    callsign_map = dict(Callsign.objects.filter(id__in=all_cs_ids).values_list("id", "callsign"))

    # Find matches and the other side's contact for sig/ref data
    contact_ids = {c.id for c in contacts}
    match_rows = list(
        Match.objects.filter(Q(a_id__in=contact_ids) | Q(b_id__in=contact_ids)).values_list(
            "a_id", "b_id", "matched_at"
        )
    )

    matched_at_map: dict[int, int] = {}
    other_contact_ids: set[int] = set()
    # Map my contact ID → other contact ID
    my_to_other: dict[int, int] = {}
    for a_id, b_id, matched_at in match_rows:
        if a_id in contact_ids:
            matched_at_map[a_id] = matched_at
            my_to_other[a_id] = b_id
            other_contact_ids.add(b_id)
        if b_id in contact_ids:
            matched_at_map[b_id] = matched_at
            my_to_other[b_id] = a_id
            other_contact_ids.add(a_id)

    # Fetch the other side's contacts for sig/ref fields
    other_contacts_map: dict[int, Contact] = {}
    if other_contact_ids:
        other_contacts_map = {
            c.id: c
            for c in Contact.objects.filter(id__in=other_contact_ids).only(
                "id", "my_pota", "my_sota", "my_wwff", "my_iota", "my_sig", "my_sig_info"
            )
        }

    # Build callsign → profile URL map (resolve via CallsignAssociation)
    to_callsigns = {callsign_map.get(c.to_id) for c in contacts} - {None, "?"}
    profile_urls: dict[str, str] = {}
    if to_callsigns:
        # Find associations for these callsigns (any user)
        assoc_qs = CallsignAssociation.objects.filter(callsign__in=to_callsigns).values_list(
            "callsign", "user_id"
        )
        for call, user_id in assoc_qs:
            # TODO: filter by date range once public profiles exist
            profile_urls[call] = f"/call/{call}/"

    rows = []
    for c in contacts:
        ts = matched_at_map.get(c.id)
        other_id = my_to_other.get(c.id)
        other = other_contacts_map.get(other_id) if other_id else None

        # Build combined sig/ref from the other station's contact
        refs = []
        if other:
            if other.my_pota:
                refs.extend(f"POTA {p}" for p in other.my_pota)
            if other.my_sota:
                refs.append(f"SOTA {other.my_sota}")
            if other.my_wwff:
                refs.append(f"WWFF {other.my_wwff}")
            if other.my_iota:
                refs.append(f"IOTA {other.my_iota}")
            if other.my_sig and other.my_sig_info:
                refs.append(f"{other.my_sig} {other.my_sig_info}")

        call_str = callsign_map.get(c.to_id, "?")
        rows.append(
            {
                "date": decode_date(c.date),
                "time": decode_time(c.time),
                "my_call": callsign_map.get(c.from_id, "?"),
                "callsign": call_str,
                "callsign_url": profile_urls.get(call_str),
                "band": decode_band(c.band),
                "mode": decode_mode(c.mode, c.sub_mode),
                "grid": decode_grid(c.grid, c.grid_size),
                "dxcc": decode_dxcc(c.dxcc),
                "cq_zone": c.zone_cq or None,
                "itu_zone": c.zone_itu or None,
                "refs": ", ".join(refs),
                "confirmed": ts is not None,
                "matched_at": datetime.fromtimestamp(ts, tz=UTC) if ts else None,
            }
        )

    return render(
        request,
        "app/logbook.html",
        {
            "rows": rows,
            "page": page,
            "has_next": has_next,
        },
    )


@login_required()
def oauth_app_list(request):
    apps = Application.objects.filter(user=request.user)
    return render(request, "app/oauth_apps.html", {"apps": apps})


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def oauth_app_create(request) -> HttpResponseRedirect:
    name = request.POST.get("name", "").strip()
    redirect_uris = request.POST.get("redirect_uris", "").strip()
    if not name:
        messages.error(request, "Application name is required.")
        return redirect("oauth-app-list")
    Application.objects.create(
        user=request.user,
        name=name,
        redirect_uris=redirect_uris,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
    )
    messages.success(request, f"Application '{name}' created.")
    return redirect("oauth-app-list")


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def oauth_app_delete(request, pk) -> HttpResponseRedirect:
    deleted, _ = Application.objects.filter(pk=pk, user=request.user).delete()
    if deleted:
        messages.success(request, "Application deleted.")
    else:
        messages.error(request, "Application not found.")
    return redirect("oauth-app-list")


async def fetch_callook(callsign: str) -> dict | None:
    url = f"https://callook.info/{callsign}/json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError, ValueError:
        return None

    if data.get("status") != "VALID":
        return None

    result: dict[str, object] = {
        "name": data.get("name", ""),
        "country": "United States",
    }
    if location := data.get("location"):
        result["grid_square"] = location.get("gridsquare", "")
        try:
            result["latitude"] = float(location["latitude"])
            result["longitude"] = float(location["longitude"])
        except KeyError, ValueError, TypeError:
            pass
    if other_info := data.get("otherInfo"):
        if grant_date := other_info.get("grantDate"):
            try:
                result["effective_date"] = datetime.strptime(grant_date, "%m/%d/%Y").strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    return result


@login_required()
async def callsign_lookup(request):
    callsign = request.GET.get("callsign", "").strip().upper()
    if not callsign:
        return JsonResponse({}, status=400)
    data = await fetch_callook(callsign)
    if data:
        return JsonResponse(data)
    return JsonResponse({}, status=404)


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def callsign_add(request) -> HttpResponseRedirect:
    callsign = request.POST.get("callsign", "").strip().upper()
    if not callsign:
        messages.error(request, "Callsign is required.")
        return redirect("profile")

    fields = {
        "name": request.POST.get("name", "").strip(),
        "country": request.POST.get("country", "").strip(),
        "grid_square": request.POST.get("grid_square", "").strip(),
    }

    if start := request.POST.get("start_date", "").strip():
        fields["start_date"] = start
    if end := request.POST.get("end_date", "").strip():
        fields["end_date"] = end

    try:
        with transaction.atomic():
            CallsignAssociation.objects.create(callsign=callsign, user=request.user, **fields)
        messages.success(request, f"Callsign {callsign} added.")
    except IntegrityError:
        messages.error(request, f"Callsign {callsign} is already in your list.")

    return redirect("profile")


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def callsign_edit(request, pk) -> HttpResponseRedirect:
    try:
        cs = CallsignAssociation.objects.get(pk=pk, user=request.user)
    except CallsignAssociation.DoesNotExist:
        messages.error(request, "Callsign not found.")
        return redirect("profile")

    cs.name = request.POST.get("name", "").strip()
    cs.country = request.POST.get("country", "").strip()
    cs.grid_square = request.POST.get("grid_square", "").strip()
    cs.start_date = request.POST.get("start_date", "").strip() or None
    cs.end_date = request.POST.get("end_date", "").strip() or None
    cs.save(update_fields=["name", "country", "grid_square", "start_date", "end_date"])
    messages.success(request, f"Callsign {cs.callsign} updated.")
    return redirect("profile")


@login_required()  # ty: ignore[invalid-argument-type]
@require_POST  # ty: ignore[invalid-argument-type]
def callsign_delete(request, pk) -> HttpResponseRedirect:
    deleted, _ = CallsignAssociation.objects.filter(pk=pk, user=request.user).delete()
    if deleted:
        messages.success(request, "Callsign removed.")
    else:
        messages.error(request, "Callsign not found.")
    return redirect("profile")
