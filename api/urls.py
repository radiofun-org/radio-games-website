from django.urls import include, path

urlpatterns = [
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]
