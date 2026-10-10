"""
config/urls.py — Root URL configuration.

Only the admin for now; the planning screens arrive in later tickets.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
