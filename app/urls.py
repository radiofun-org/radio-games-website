from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

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
    path("faq/", RedirectView.as_view(pattern_name="how-it-works", permanent=True)),
    path("how-it-works/", views.how_it_works, name="how-it-works"),
    path("privacy/", views.privacy, name="privacy"),
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("profile/", views.profile, name="profile"),
    path("profile/api-key/reset/", views.api_key_reset, name="api-key-reset"),
    path("profile/delete-account/", views.account_delete, name="account-delete"),
    path("profile/apps/", views.oauth_app_list, name="oauth-app-list"),
    path("profile/apps/create/", views.oauth_app_create, name="oauth-app-create"),
    path("profile/apps/<int:pk>/delete/", views.oauth_app_delete, name="oauth-app-delete"),
    path("profile/callsign/add/", views.callsign_add, name="callsign-add"),
    path("profile/callsign/lookup/", views.callsign_lookup, name="callsign-lookup"),
    path("profile/callsign/<int:pk>/edit/", views.callsign_edit, name="callsign-edit"),
    path("profile/callsign/<int:pk>/delete/", views.callsign_delete, name="callsign-delete"),
    path("call/<str:callsign>/", views.public_callsign, name="public-callsign"),
    path("logbook/", views.logbook, name="logbook"),
    path("upload/", views.upload, name="upload"),
]
