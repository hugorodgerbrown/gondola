"""apps/tour/urls.py — Onboarding tour URLs (namespace ``tour``)."""

from django.urls import path

from . import views

app_name = "tour"

urlpatterns = [
    path("tour/", views.offer, name="offer"),
    path("tour/start/", views.start, name="start"),
    path("tour/end/", views.end, name="end"),
    path("tour/finish/", views.finish, name="finish"),
]
