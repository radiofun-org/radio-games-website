from datetime import datetime

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
    callsign_ids = list(callsigns.values_list("id", flat=True))

    match_count = 0
    if callsign_ids:
        try:
            from contacts.models import Match

            match_count = Match.objects.filter(
                Q(a_call_id__in=callsign_ids) | Q(b_call_id__in=callsign_ids)
            ).count()
        except Exception:
            pass

    return render(request, "app/profile.html", {
        "upload_count": upload_count,
        "contact_count": len(callsign_ids),
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
