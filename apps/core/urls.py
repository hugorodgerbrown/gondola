"""apps/core/urls.py — The front page and app plumbing (namespace ``core``)."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
    # Health checks: /livez for Render (process up), /healthz adds the database.
    path("livez", views.livez, name="livez"),
    path("healthz", views.healthz, name="healthz"),
]
