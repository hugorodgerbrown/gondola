"""apps/core/urls.py — The health checks and security.txt (namespace ``core``)."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    # /livez for Render (process up); /healthz adds the database.
    path("livez", views.livez, name="livez"),
    path("healthz", views.healthz, name="healthz"),
    # RFC 9116: who to tell about a vulnerability.
    path(".well-known/security.txt", views.security_txt, name="security-txt"),
]
