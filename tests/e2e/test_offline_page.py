"""A page never visited shows the offline page, not the browser's error.

Scenario: offline fallback (docs/testing.md, "Journeys").
"""

from typing import Any

from playwright.sync_api import Page, expect


def test_unvisited_page_offline_shows_the_offline_page(
    signed_in_page: Page, live_server: Any
) -> None:
    """The worker answers a navigation it can't serve with the offline page."""
    signed_in_page.context.set_offline(True)
    signed_in_page.goto(f"{live_server.url}/app/groups/?never-visited=1")
    expect(signed_in_page.get_by_role("heading", name="No signal")).to_be_visible()


def test_a_visited_page_opens_offline(signed_in_page: Page, live_server: Any) -> None:
    """The calendar, opened once, opens again with no connection."""
    signed_in_page.context.set_offline(True)
    signed_in_page.goto(f"{live_server.url}/app/days/")
    expect(signed_in_page.locator("[data-offline-banner]")).to_be_visible()
    expect(signed_in_page.get_by_role("link", name="Calendar")).to_be_visible()
