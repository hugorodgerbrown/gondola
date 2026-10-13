"""apps/tour/urls.py — Onboarding tour URLs (namespace ``tour``)."""

from django.urls import path

from . import views

app_name = "tour"

urlpatterns = [
    path("app/tour/", views.offer, name="offer"),
    path("app/tour/start/", views.start, name="start"),
    path("app/tour/end/", views.end, name="end"),
    path("app/tour/finish/", views.finish, name="finish"),
]
