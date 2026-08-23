from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from api.views import api as ninja_api

from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=EmailAuthenticationForm),
        name="login",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("api/docs", views.api_docs, name="api-docs"),
    path("api/", ninja_api.urls),
    path("faq/", views.faq, name="faq"),
    path("how-it-works/", views.how_it_works, name="how-it-works"),
    path("profile/", views.profile, name="profile"),
    path("profile/api-key/reset/", views.api_key_reset, name="api-key-reset"),
    path("profile/callsign/add/", views.callsign_add, name="callsign-add"),
    path("profile/callsign/lookup/", views.callsign_lookup, name="callsign-lookup"),
    path("profile/callsign/<int:pk>/edit/", views.callsign_edit, name="callsign-edit"),
    path("profile/callsign/<int:pk>/delete/", views.callsign_delete, name="callsign-delete"),
    path("call/<str:callsign>/", views.public_callsign, name="public-callsign"),
    path("logbook/", views.logbook, name="logbook"),
    path("upload/", views.upload, name="upload"),
]
