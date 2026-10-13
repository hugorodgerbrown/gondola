"""Root URL configuration.

Public pages (the front page, terms, privacy, help), signing in and out,
invite links and the health checks sit at the root. The installed app is
everything under /app/ (``apps.pwa.conf.SCOPE``): the planning screens,
the account page and the tour, whose apps write their own ``app/``
prefixes. The MCP endpoint is ``/mcp``, with mcp-auth's OAuth URLs
(``/.well-known/…``, ``/oauth/…``) at the root. The admin carries the product name.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.mcp.views import mcp

admin.site.site_header = settings.SITE_NAME
admin.site.site_title = settings.SITE_NAME

urlpatterns = [
    # Public: the front page, terms, privacy and help.
    path("", include("apps.public.urls")),
    path("admin/", admin.site.urls),
    # Health checks.
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    # The installed app: everything under /app/ (apps/pwa/conf.py: SCOPE).
    path("app/", include("apps.pwa.urls")),
    path("", include("apps.groups.urls")),
    path("", include("apps.tour.urls")),
    path("", include("mcp_auth.urls")),
    path("mcp", mcp, name="mcp"),
]
