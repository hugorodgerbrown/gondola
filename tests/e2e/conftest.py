"""Fixtures for the Playwright journeys: a live server and a signed-in page."""

import os
import re
from typing import Any

import pytest
from playwright.sync_api import Page

from tests.factories import UserFactory


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Use a preinstalled Chromium when PLAYWRIGHT_CHROMIUM_EXECUTABLE names one.

    Cloud sandboxes ship a browser but block Playwright's download; CI
    installs its own and leaves this unset.
    """
    if path := os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"):
        return {**browser_type_launch_args, "executable_path": path}
    return browser_type_launch_args


@pytest.fixture
def signed_in_page(
    page: Page, live_server: Any, mailoutbox: list[Any], settings: Any, transactional_db: None
) -> Page:
    """A page signed in by emailed code, on the calendar, controlled by the service worker.

    The code, not the link, because it is the way in from an installed
    iPhone app. The server runs in this process, so the email lands in
    ``mailoutbox``. Passkeys are checked against the live server's origin.
    The account already has a name, so sign-in goes straight to the calendar.
    """
    settings.WEBAUTHN_ORIGINS = [live_server.url]
    UserFactory.create(email="walker@example.com", display_name="Walker")
    page.goto(f"{live_server.url}/sign-in/?next=/app/days/")
    page.get_by_label("Email").fill("walker@example.com")
    page.get_by_role("button", name="Email me a link").click()
    page.wait_for_url("**/sign-in/code/")
    code = re.search(r"^(\d{6})$", mailoutbox[-1].body, re.MULTILINE)
    assert code, mailoutbox[-1].body
    # Six digit boxes: the whole code typed into the first fills them all and submits.
    page.get_by_label("Code").fill(code.group(1))
    page.wait_for_url("**/app/days/")
    # The first load installs the worker; it takes control without a reload.
    # (evaluate, not wait_for_function: the page's CSP forbids the eval the latter uses.)
    page.evaluate(
        """() => navigator.serviceWorker.controller || new Promise((resolve) =>
            navigator.serviceWorker.addEventListener("controllerchange", resolve))"""
    )
    # Load once more through the worker, so this page is cached for offline.
    page.reload()
    return page
