"""tests/core/test_staticfiles.py — collectstatic with the production storage.

Development serves static files unhashed, so a broken reference inside a
vendored file (such as a source map comment pointing at a file we don't
ship) only shows up when the manifest storage post-processes it on deploy.
This runs that step in the test suite instead.
"""

from pathlib import Path

from django.core.management import call_command
from django.test import override_settings

PRODUCTION_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}


def test_collectstatic_succeeds_with_manifest_storage(tmp_path: Path) -> None:
    """Every static file and every URL it references can be hashed."""
    with override_settings(STORAGES=PRODUCTION_STORAGES, STATIC_ROOT=tmp_path):
        call_command("collectstatic", interactive=False, verbosity=0)
    assert (tmp_path / "staticfiles.json").exists()
