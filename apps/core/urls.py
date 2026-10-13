"""apps/core/urls.py — The health checks (namespace ``core``)."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    # /livez for Render (process up); /healthz adds the database.
    path("livez", views.livez, name="livez"),
    path("healthz", views.healthz, name="healthz"),
]
