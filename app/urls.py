from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup/", views.SignUpView.as_view(), name="signup"),
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
]
