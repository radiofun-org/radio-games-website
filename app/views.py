from datetime import datetime, timezone

import httpx
import redis
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from contacts.decode import (
    decode_band,
    decode_date,
    decode_dxcc,
    decode_grid,
    decode_mode,
    decode_time,
)
from contacts.models import Callsign, Contact, Match

from .forms import LoginForm, LogUploadForm, SignUpForm
from .models import CallsignAssociation, LogUpload, generate_api_key

BACKEND = "django.contrib.auth.backends.ModelBackend"


def index(request):
    if request.user.is_authenticated:
        return render(request, "app/index.html")

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

    return render(request, "app/index.html", {
        "signup_form": signup_form,
        "login_form": login_form,
        "is_login": is_login,
    })


def api_docs(request):
    return render(request, "app/api_docs.html")


def about(request):
    return render(request, "app/about.html")


def faq(request):
    return render(request, "app/faq.html")


def how_it_works(request):
    return render(request, "app/how-it-works.html")


@login_required
def upload(request):
    if request.method == "POST":
        form = LogUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            log_upload = LogUpload(
                log_file=form.cleaned_data["log_file"],
                callsign=form.cleaned_data["callsign"],
                user=request.user,
            )
            log_upload.save()

            r = redis.from_url(settings.REDIS_URL)
            r.lpush("log_upload_queue", log_upload.id)

            messages.success(request, "Log uploaded successfully! It will be processed shortly.")
            return redirect("upload")
    else:
        form = LogUploadForm(user=request.user)
    recent_uploads = LogUpload.objects.filter(user=request.user).order_by("-upload_time")[:10]
    return render(request, "app/upload.html", {"form": form, "recent_uploads": recent_uploads})


@login_required
def profile(request):
    user = request.user
    callsigns = CallsignAssociation.objects.filter(user=user)
    upload_count = LogUpload.objects.filter(user=user).count()
    user_callsign_strs = list(callsigns.values_list("callsign", flat=True))

    matcher_ids = list(
        Callsign.objects.filter(callsign__in=user_callsign_strs).values_list("id", flat=True)
    )
    match_count = (
        Match.objects.filter(
            Q(a_call_id__in=matcher_ids) | Q(b_call_id__in=matcher_ids)
        ).count()
        if matcher_ids
        else 0
    )

    return render(request, "app/profile.html", {
        "upload_count": upload_count,
        "contact_count": len(user_callsign_strs),
        "match_count": match_count,
        "callsigns": callsigns,
    })


@login_required
@require_POST
def api_key_reset(request):
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
    contact_count = Contact.objects.filter(
        Q(from_id=matcher_id) | Q(to_id=matcher_id)
    ).count()
    match_count = Match.objects.filter(
        Q(a_call_id=matcher_id) | Q(b_call_id=matcher_id)
    ).count()

    return render(request, "app/public_callsign.html", {
        "callsign": callsign,
        "found": True,
        "assoc": assoc,
        "contact_count": contact_count,
        "match_count": match_count,
    })


LOGBOOK_PAGE_SIZE = 100


@login_required
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
        Contact.objects.filter(from_id__in=matcher_ids)
        .order_by("-date", "-time")[offset : offset + LOGBOOK_PAGE_SIZE + 1]
    )
    has_next = len(contacts) > LOGBOOK_PAGE_SIZE
    contacts = contacts[:LOGBOOK_PAGE_SIZE]

    # Resolve callsign IDs → strings (both from and to)
    all_cs_ids = {c.to_id for c in contacts} | {c.from_id for c in contacts}
    callsign_map = dict(Callsign.objects.filter(id__in=all_cs_ids).values_list("id", "callsign"))

    # Find matches and the other side's contact for sig/ref data
    contact_ids = {c.id for c in contacts}
    match_rows = list(
        Match.objects.filter(
            Q(a_id__in=contact_ids) | Q(b_id__in=contact_ids)
        ).values_list("a_id", "b_id", "matched_at")
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
        assoc_qs = CallsignAssociation.objects.filter(
            callsign__in=to_callsigns
        ).values_list("callsign", "user_id")
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
        rows.append({
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
            "matched_at": datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
        })

    return render(request, "app/logbook.html", {
        "rows": rows,
        "page": page,
        "has_next": has_next,
    })


async def fetch_callook(callsign: str) -> dict | None:
    url = f"https://callook.info/{callsign}/json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
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
        except (KeyError, ValueError, TypeError):
            pass
    if other_info := data.get("otherInfo"):
        if grant_date := other_info.get("grantDate"):
            try:
                result["effective_date"] = datetime.strptime(
                    grant_date, "%m/%d/%Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return result


@login_required
async def callsign_lookup(request):
    callsign = request.GET.get("callsign", "").strip().upper()
    if not callsign:
        return JsonResponse({}, status=400)
    data = await fetch_callook(callsign)
    if data:
        return JsonResponse(data)
    return JsonResponse({}, status=404)


@login_required
@require_POST
def callsign_add(request):
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


@login_required
@require_POST
def callsign_edit(request, pk):
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


@login_required
@require_POST
def callsign_delete(request, pk):
    deleted, _ = CallsignAssociation.objects.filter(pk=pk, user=request.user).delete()
    if deleted:
        messages.success(request, "Callsign removed.")
    else:
        messages.error(request, "Callsign not found.")
    return redirect("profile")
