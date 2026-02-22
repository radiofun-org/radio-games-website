from django.contrib import admin
from django.urls import include, path

from api import views as api_views

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("api/", api_views.documentation, name="api-documentation"),
    path("api/", include("api.urls")),
    path("faq/", views.faq, name="faq"),
    path("how-it-works/", views.how_it_works, name="how-it-works"),
    path("profile/", views.profile, name="profile"),
    path("profile/callsign/add/", views.callsign_add, name="callsign-add"),
    path("profile/callsign/<int:pk>/delete/", views.callsign_delete, name="callsign-delete"),
    path("upload/", views.upload, name="upload"),
]
