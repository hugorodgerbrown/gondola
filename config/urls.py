"""
config/urls.py — Root URL configuration.

Everything is mounted at the root: the front page and app plumbing under
``core``, sign-in and the account page under ``accounts``, and the
planning screens (map, days, groups, meet-ups) under ``planning``. The
admin carries the product name rather than Django's default.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = settings.SITE_NAME
admin.site.site_title = settings.SITE_NAME

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.groups.urls")),
]
