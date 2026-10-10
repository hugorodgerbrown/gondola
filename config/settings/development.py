"""
config/settings/development.py — Local development and test settings.

Defaults ``DEBUG`` on and supplies a throwaway ``SECRET_KEY`` so a fresh
checkout runs without a ``.env``.
"""

import os

os.environ.setdefault("SECRET_KEY", "dev-insecure-secret-key")

from .base import *  # noqa: E402, F403 — settings overlay pattern

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Static files are served by runserver locally; skip the manifest so tests
# don't need collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
